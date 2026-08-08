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
    jobs_df = scrape_jobs(
        site_name=[site_name],
        search_term=search_term,
        location=location,
        results_wanted=results_wanted,
        hours_old=72,
    )
    saved_vacancies: List[Vacancy] = []
    if jobs_df.empty:
        return saved_vacancies

    source_enum = DataSource.linkedin if site_name.lower() == "linkedin" else DataSource.other

    for _, row in jobs_df.iterrows():
        vacancy = save_vacancy(
            title=str(row.get("title") or "Unknown Title"),
            text=str(row.get("description") or ""),
            credentials=str(row.get("emails") or ""),
            url=str(row.get("job_url") or ""),
            source=source_enum,
            visa_status=VisaStatus.not_mentioned,
            db=db,
        )
        saved_vacancies.append(vacancy)
    return saved_vacancies

run_jobspy_harness = fetch_and_store_jobs
