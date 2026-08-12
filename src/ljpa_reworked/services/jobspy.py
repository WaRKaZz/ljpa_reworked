import hashlib
import logging
import os
import uuid
from pathlib import Path
from typing import Any

import pandas as pd
from jobspy import scrape_jobs
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from ljpa_reworked.models.crewai_pydantic_models import (
    JobSearchQuery,
    JobSearchQuerySet,
    VisaStatus,
)
from ljpa_reworked.models.database_models import DataSource, Vacancy
from ljpa_reworked.operations.vacancy_ops import upsert_vacancy_by_url

logger = logging.getLogger(__name__)


class JobSpyRunSummary(BaseModel):
    """Summary of a JobSpy search run."""

    queries_attempted: int = 0
    rows_received: int = 0
    created_count: int = 0
    refreshed_count: int = 0
    skipped_without_url_count: int = 0
    failures_by_query: list[dict] = Field(default_factory=list)


# Dynamic resolution of project/package root directory (NOT dependent on os.getcwd())
# src/ljpa_reworked/services/jobspy.py -> parents[3] is project root
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PROFILE_PATH = PROJECT_ROOT / "resources" / "profile.md"
DEFAULT_CACHE_PATH = PROJECT_ROOT / "resources" / "profile_search_query.json"


def compute_profile_sha256(profile_path: Path) -> tuple[str, str]:
    """Read profile text from UTF-8 file and return (profile_text, sha256_hash)."""
    if not profile_path.exists():
        raise FileNotFoundError(f"Profile file not found at: {profile_path}")
    profile_bytes = profile_path.read_bytes()
    profile_sha256 = hashlib.sha256(profile_bytes).hexdigest()
    profile_text = profile_bytes.decode("utf-8")
    return profile_text, profile_sha256


def load_cached_queries(
    cache_path: Path, expected_sha256: str
) -> JobSearchQuerySet | None:
    """Load and validate cached JobSearchQuerySet if present and profile_sha256 matches."""
    if not cache_path.exists():
        logger.info("Cache file %s does not exist.", cache_path)
        return None
    try:
        content = cache_path.read_text(encoding="utf-8")
        query_set = JobSearchQuerySet.model_validate_json(content)
        if query_set.profile_sha256 != expected_sha256:
            logger.info(
                "Cache SHA256 (%s) does not match profile SHA256 (%s).",
                query_set.profile_sha256,
                expected_sha256,
            )
            return None
        return query_set
    except (ValidationError, Exception) as err:
        logger.warning("Failed to load or validate cache from %s: %s", cache_path, err)
        return None


def atomic_write_cache(cache_path: Path, query_set: JobSearchQuerySet) -> None:
    """Atomically write JobSearchQuerySet to cache file via a temporary sibling file."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = cache_path.with_name(f"{cache_path.name}.tmp.{uuid.uuid4().hex}")
    json_str = query_set.model_dump_json(indent=2)
    with open(temp_path, "w", encoding="utf-8") as f:
        f.write(json_str)
        f.flush()
        os.fsync(f.fileno())
    temp_path.replace(cache_path)


def generate_and_cache_queries(
    profile_path: Path,
    cache_path: Path,
    crew_runner: Any | None = None,
) -> JobSearchQuerySet:
    """Kick off QueryGenerationCrew to generate queries and write atomically to cache."""
    profile_text, profile_sha256 = compute_profile_sha256(profile_path)
    try:
        if crew_runner is not None:
            result = crew_runner(
                profile_text=profile_text, profile_sha256=profile_sha256
            )
        else:
            from ljpa_reworked.crews.query_generation_crew.query_generation_crew import (
                QueryGenerationCrew,
            )

            kickoff_res = (
                QueryGenerationCrew()
                .crew()
                .kickoff(
                    inputs={
                        "profile_text": profile_text,
                        "profile_sha256": profile_sha256,
                    }
                )
            )
            if hasattr(kickoff_res, "pydantic") and kickoff_res.pydantic:
                result = kickoff_res.pydantic
            elif hasattr(kickoff_res, "raw") and kickoff_res.raw:
                result = JobSearchQuerySet.model_validate_json(kickoff_res.raw)
            else:
                result = kickoff_res

        if isinstance(result, JobSearchQuerySet):
            query_set = result
        elif isinstance(result, str):
            query_set = JobSearchQuerySet.model_validate_json(result)
        elif isinstance(result, dict):
            query_set = JobSearchQuerySet.model_validate(result)
        else:
            query_set = JobSearchQuerySet.model_validate(result)

        if query_set.profile_sha256 != profile_sha256:
            raise ValueError(
                "CrewAI profile_sha256 does not match the current profile content"
            )

        atomic_write_cache(cache_path, query_set)
        return query_set
    except Exception as e:
        logger.error("CrewAI query generation failed: %s", e)
        raise RuntimeError(f"CrewAI query generation failed: {e}") from e


def get_or_generate_job_search_queries(
    profile_path: Path | None = None,
    cache_path: Path | None = None,
    crew_runner: Any | None = None,
) -> JobSearchQuerySet:
    """Return cached queries if profile SHA256 matches; otherwise generate new queries and update cache."""
    p_path = profile_path or DEFAULT_PROFILE_PATH
    c_path = cache_path or DEFAULT_CACHE_PATH
    _, current_sha = compute_profile_sha256(p_path)

    cached_set = load_cached_queries(c_path, current_sha)
    if cached_set is not None:
        logger.info(
            "Using cached JobSearchQuerySet with matching SHA256: %s", current_sha
        )
        return cached_set

    logger.info("Cache miss or profile changed. Generating queries via CrewAI...")
    return generate_and_cache_queries(p_path, c_path, crew_runner=crew_runner)


def normalize_and_deduplicate_queries(
    queries: list[JobSearchQuery],
) -> list[JobSearchQuery]:
    """Normalize and deduplicate queries by key (site_name, search_term.lower().strip(), location.lower().strip())."""
    seen = set()
    deduped: list[JobSearchQuery] = []
    for q in queries:
        key = (
            q.site_name,
            q.search_term.lower().strip(),
            q.location.lower().strip(),
        )
        if key not in seen:
            seen.add(key)
            deduped.append(q)
    return deduped


def validate_jobspy_query(site_name: str, location: str) -> str | None:
    """Validate query against source capabilities. Returns skip reason string if unsupported, None if supported."""
    site = (site_name or "").lower().strip()
    loc = (location or "").lower().strip()
    if site in ("zip_recruiter", "ziprecruiter"):
        return "ZipRecruiter source is currently unavailable in this environment"
    if site == "glassdoor" and loc == "worldwide":
        return "Glassdoor does not support worldwide location search"
    return None


class JobSpyIntegrationService:
    """Service orchestrating sequential JobSpy search, caching, and database upserts."""

    def __init__(
        self,
        profile_path: Path | None = None,
        cache_path: Path | None = None,
        crew_runner: Any | None = None,
    ):
        self.profile_path = profile_path or DEFAULT_PROFILE_PATH
        self.cache_path = cache_path or DEFAULT_CACHE_PATH
        self.crew_runner = crew_runner

    def get_queries(self) -> list[JobSearchQuery]:
        """Fetch, cache/validate, and return normalized, deduplicated search queries."""
        query_set = get_or_generate_job_search_queries(
            profile_path=self.profile_path,
            cache_path=self.cache_path,
            crew_runner=self.crew_runner,
        )
        return normalize_and_deduplicate_queries(query_set.queries)

    def run(self, db: Session | None = None) -> JobSpyRunSummary:
        """Run JobSpy search pipeline over all derived search queries.

        Obtains queries via get_queries(), iterates over queries, calls scrape_jobs for each,
        upserts vacancies by URL, aggregates counters, and returns JobSpyRunSummary.
        This is Step 2 of the sequential pipeline; later stages own review, resumes, and application.
        """
        import pandas as pd

        queries = self.get_queries()
        summary = JobSpyRunSummary()

        def _execute_discovery(session: Session) -> None:
            for q in queries:
                summary.queries_attempted += 1
                q_dict = (
                    q.model_dump()
                    if hasattr(q, "model_dump")
                    else {
                        "search_term": q.search_term,
                        "site_name": q.site_name,
                        "location": q.location,
                    }
                )
                skip_reason = validate_jobspy_query(q.site_name, q.location)
                if skip_reason:
                    logger.warning("Skipping query %s: %s", q, skip_reason)
                    summary.failures_by_query.append(
                        {"query": q_dict, "error": skip_reason}
                    )
                    continue

                try:
                    scrape_kwargs = {
                        "site_name": [q.site_name],
                        "search_term": q.search_term,
                        "location": q.location,
                        "results_wanted": q.results_wanted,
                        "hours_old": 72,
                        "country_indeed": "worldwide",
                    }
                    if q.site_name == "google" and getattr(q, "google_search_term", None):
                        scrape_kwargs["google_search_term"] = q.google_search_term

                    jobs_df = scrape_jobs(**scrape_kwargs)
                except Exception as err:
                    logger.error("JobSpy scrape failed for query %s: %s", q, err)
                    summary.failures_by_query.append(
                        {"query": q_dict, "error": str(err)}
                    )
                    continue

                if jobs_df is None or jobs_df.empty:
                    continue

                site_str = q.site_name.lower()
                source_enum = (
                    DataSource.linkedin
                    if site_str == "linkedin"
                    else (
                        DataSource[site_str]
                        if site_str in DataSource.__members__
                        else DataSource.other
                    )
                )

                for _, row in jobs_df.iterrows():
                    summary.rows_received += 1
                    raw_url = row.get("job_url")
                    if raw_url is None or pd.isna(raw_url):
                        trimmed_url = ""
                    else:
                        trimmed_url = str(raw_url).strip()

                    if not trimmed_url or trimmed_url.lower() == "nan":
                        logger.info(
                            "Skipping JobSpy row with empty or invalid job_url."
                        )
                        summary.skipped_without_url_count += 1
                        continue

                    raw_emails = row.get("emails")
                    email_val = (
                        str(raw_emails).strip()
                        if raw_emails is not None
                        and not pd.isna(raw_emails)
                        and str(raw_emails).strip()
                        else None
                    )

                    vacancy_data = {
                        "title": str(row.get("title") or "Unknown Title"),
                        "text": str(row.get("description") or ""),
                        "submit_email": email_val,
                        "submit_url": trimmed_url,
                        "source": source_enum,
                        "visa_status": VisaStatus.not_mentioned,
                    }

                    vacancy, is_created = upsert_vacancy_by_url(session, vacancy_data)
                    if vacancy is None:
                        summary.skipped_without_url_count += 1
                    elif is_created:
                        summary.created_count += 1
                    else:
                        summary.refreshed_count += 1

        if db is not None:
            _execute_discovery(db)
        else:
            from ljpa_reworked.database import SessionLocal

            with SessionLocal() as session:
                _execute_discovery(session)

        logger.info(
            "JobSpy search completed: attempted=%d, rows=%d, created=%d, refreshed=%d, skipped=%d, failures=%d",
            summary.queries_attempted,
            summary.rows_received,
            summary.created_count,
            summary.refreshed_count,
            summary.skipped_without_url_count,
            len(summary.failures_by_query),
        )
        return summary


def _store_jobs_df(
    jobs_df: Any, source_enum: DataSource, session: Session
) -> list[Vacancy]:
    seen_urls: set[str] = set()
    saved_vacancies: list[Vacancy] = []

    for _, row in jobs_df.iterrows():
        raw_url = row.get("job_url")
        if raw_url is None:
            raw_url = ""
        trimmed_url = str(raw_url).strip()
        if not trimmed_url:
            logger.info("Skipping JobSpy row with empty job_url.")
            continue

        if trimmed_url in seen_urls:
            logger.info(
                "Skipping duplicate job_url '%s' within same scrape batch.", trimmed_url
            )
            continue

        seen_urls.add(trimmed_url)

        raw_emails = row.get("emails")
        email_val = (
            str(raw_emails).strip()
            if raw_emails is not None
            and not pd.isna(raw_emails)
            and str(raw_emails).strip()
            else None
        )

        vacancy_data = {
            "title": str(row.get("title") or "Unknown Title"),
            "text": str(row.get("description") or ""),
            "submit_email": email_val,
            "submit_url": trimmed_url,
            "source": source_enum,
            "visa_status": VisaStatus.not_mentioned,
        }

        vacancy, _ = upsert_vacancy_by_url(session, vacancy_data)
        if vacancy is not None:
            saved_vacancies.append(vacancy)

    logger.info("Successfully processed %d vacancy records.", len(saved_vacancies))
    return saved_vacancies


def fetch_and_store_jobs(
    site_name: str = "linkedin",
    search_term: str = "Python Developer",
    location: str = "Remote",
    results_wanted: int = 10,
    db: Session | None = None,
    google_search_term: str | None = None,
) -> list[Vacancy]:
    """Fetch job postings via python-jobspy ETL pipeline and store them as Vacancy records in SQLite."""
    logger.info(
        "Executing JobSpy scrape for '%s' in '%s' on %s...",
        search_term,
        location,
        site_name,
    )
    skip_reason = validate_jobspy_query(site_name, location)
    if skip_reason:
        logger.warning("Skipping JobSpy scrape: %s", skip_reason)
        return []

    try:
        scrape_kwargs = {
            "site_name": [site_name],
            "search_term": search_term,
            "location": location,
            "results_wanted": results_wanted,
            "hours_old": 72,
            "country_indeed": "worldwide",
        }
        if site_name == "google" and google_search_term:
            scrape_kwargs["google_search_term"] = google_search_term

        jobs_df = scrape_jobs(**scrape_kwargs)
    except Exception as err:
        logger.error(
            "JobSpy scrape failed for %s (%s, %s): %s",
            site_name,
            search_term,
            location,
            err,
        )
        return []

    if jobs_df is None or jobs_df.empty:
        logger.warning("JobSpy returned no results.")
        return []

    source_enum = (
        DataSource.linkedin if site_name.lower() == "linkedin" else DataSource.other
    )

    if db is not None:
        return _store_jobs_df(jobs_df, source_enum, db)

    from ljpa_reworked.database import SessionLocal

    with SessionLocal() as session:
        return _store_jobs_df(jobs_df, source_enum, session)
