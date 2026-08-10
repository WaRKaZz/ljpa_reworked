import hashlib
import logging
import os
import uuid
from pathlib import Path
from typing import Any, List

from jobspy import scrape_jobs
from pydantic import ValidationError
from sqlalchemy.orm import Session

from ljpa_reworked.models.crewai_pydantic_models import (
    JobSearchQuery,
    JobSearchQuerySet,
    VisaStatus,
)
from ljpa_reworked.models.database_models import DataSource, Vacancy
from ljpa_reworked.operations.vacancy_ops import upsert_vacancy_by_url

logger = logging.getLogger(__name__)

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


def load_cached_queries(cache_path: Path, expected_sha256: str) -> JobSearchQuerySet | None:
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
            result = crew_runner(profile_text=profile_text, profile_sha256=profile_sha256)
        else:
            from ljpa_reworked.crews.query_generation_crew.query_generation_crew import (
                QueryGenerationCrew,
            )

            kickoff_res = QueryGenerationCrew().crew().kickoff(
                inputs={"profile_text": profile_text, "profile_sha256": profile_sha256}
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
            query_set = query_set.model_copy(update={"profile_sha256": profile_sha256})

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
        logger.info("Using cached JobSearchQuerySet with matching SHA256: %s", current_sha)
        return cached_set

    logger.info("Cache miss or profile changed. Generating queries via CrewAI...")
    return generate_and_cache_queries(p_path, c_path, crew_runner=crew_runner)


def normalize_and_deduplicate_queries(queries: list[JobSearchQuery]) -> list[JobSearchQuery]:
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


class JobSpyIntegrationService:
    """Service orchestrating search query generation, caching, and JobSpy discovery."""

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


def _store_jobs_df(jobs_df: Any, source_enum: DataSource, session: Session) -> List[Vacancy]:
    seen_urls: set[str] = set()
    saved_vacancies: List[Vacancy] = []

    for _, row in jobs_df.iterrows():
        raw_url = row.get("job_url")
        if raw_url is None:
            raw_url = ""
        trimmed_url = str(raw_url).strip()
        if not trimmed_url:
            logger.info("Skipping JobSpy row with empty job_url.")
            continue

        if trimmed_url in seen_urls:
            logger.info("Skipping duplicate job_url '%s' within same scrape batch.", trimmed_url)
            continue

        seen_urls.add(trimmed_url)

        vacancy_data = {
            "title": str(row.get("title") or "Unknown Title"),
            "text": str(row.get("description") or ""),
            "credentials": str(row.get("emails")) if row.get("emails") is not None else None,
            "url": trimmed_url,
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
) -> List[Vacancy]:
    """Fetch job postings via python-jobspy ETL pipeline and store them as Vacancy records in SQLite."""
    logger.info("Executing JobSpy scrape for '%s' in '%s' on %s...", search_term, location, site_name)
    jobs_df = scrape_jobs(
        site_name=[site_name],
        search_term=search_term,
        location=location,
        results_wanted=results_wanted,
        hours_old=72,
    )
    if jobs_df.empty:
        logger.warning("JobSpy returned no results.")
        return []

    source_enum = DataSource.linkedin if site_name.lower() == "linkedin" else DataSource.other

    if db is not None:
        return _store_jobs_df(jobs_df, source_enum, db)

    from ljpa_reworked.database import SessionLocal

    with SessionLocal() as session:
        return _store_jobs_df(jobs_df, source_enum, session)

