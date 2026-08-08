import logging
from typing import List

from jobspy import scrape_jobs
from sqlalchemy.orm import Session

from ljpa_reworked.models.crewai_pydantic_models import VisaStatus
from ljpa_reworked.models.database_models import DataSource, Vacancy
from ljpa_reworked.operations.vacancy_ops import save_vacancy

logger = logging.getLogger(__name__)


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

    saved_vacancies: List[Vacancy] = []
    if jobs_df.empty:
        logger.warning("JobSpy returned no results.")
        return saved_vacancies

    source_enum = DataSource.linkedin if site_name.lower() == "linkedin" else DataSource.other

    for _, row in jobs_df.iterrows():
        title = str(row.get("title") or "Unknown Title")
        text = str(row.get("description") or "")
        url = str(row.get("job_url") or "")
        emails = str(row.get("emails") or "")

        vacancy = save_vacancy(
            title=title,
            text=text,
            credentials=emails,
            url=url,
            source=source_enum,
            visa_status=VisaStatus.not_mentioned,
            db=db,
        )
        saved_vacancies.append(vacancy)

    logger.info("Successfully fetched and saved %d vacancy records.", len(saved_vacancies))
    return saved_vacancies
