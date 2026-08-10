#!/usr/bin/env python
import logging
from typing import cast

from ljpa_reworked.crew_workflow import (
    crewai_evaluate_vacancy,
    crewai_generate_email,
    crewai_generate_resume,
)
from ljpa_reworked.database import SessionLocal
from ljpa_reworked.models.enums import VacancyStatus
from ljpa_reworked.operations import (
    create_email,
    create_evaluation,
    get_eligble_vacancies,
    transition_vacancy_status,
)
from ljpa_reworked.services.harness_runner import run_linkedin_harness
from ljpa_reworked.services.jobspy import fetch_and_store_jobs
from ljpa_reworked.workflow import (  # noqa
    extract_email,
    get_linkedin_posts,
    process_linkedin_posts,
    save_resume,
    save_vacancies,
    send_email,
    send_telegram_post,
    verified_recipient,
)

logger = logging.getLogger(__name__)


def main():
    logger.info("=== STARTING SEQUENTIAL AGENTIC PIPELINE ===")

    # Step 1: Execute Harness Scraper (LinkedIn Posts Search Agent)
    logger.info("[Step 1/4] Executing Harness Scraper (LinkedIn Posts Search Agent)...")
    run_linkedin_harness()

    # Step 2: Execute Harness 2 (JobSpy Official Job Postings) synchronously
    logger.info("[Step 2/4] Executing Harness 2 (Official LinkedIn Job Postings ETL)...")
    try:
        fetch_and_store_jobs(search_term="Automation Engineer", results_wanted=5)
        fetch_and_store_jobs(search_term="PLC Programmer", results_wanted=5)
    except Exception as e:
        logger.error(f"Harness 2 execution warning: {e}")

    # Step 3: Process and Evaluate Vacancies Sequentially
    logger.info("[Step 3/4] Evaluating candidate vacancies sequentially...")
    with SessionLocal() as db:
        posts = get_linkedin_posts(db)
        if posts:
            vacancies = process_linkedin_posts(posts=posts, db=db)
            save_vacancies(vacancies, db)

        vacancies = get_eligble_vacancies(db=db)
        logger.info("Found %d eligible vacancies for evaluation.", len(vacancies))
        for vacancy in vacancies:
            vacancy_credentials = cast(str, vacancy.credentials or "")
            evaluation = crewai_evaluate_vacancy(vacancy=vacancy)
            create_evaluation(
                db=db,
                vacancy_id=vacancy.id,
                evaluation_data=evaluation,
            )
            if not evaluation.rating > 50:
                transition_vacancy_status(
                    db=db,
                    vacancy_id=vacancy.id,
                    target_status=VacancyStatus.rejected,
                )
                continue

            resume = crewai_generate_resume(vacancy=vacancy, evaluation=evaluation)
            orm_resume = save_resume(resume, vacancy, db)

            recipient_email = extract_email(vacancy_credentials)
            if not recipient_email:
                send_telegram_post(vacancy=vacancy, db=db)
                transition_vacancy_status(
                    db=db,
                    vacancy_id=vacancy.id,
                    target_status=VacancyStatus.application_prepared,
                )
                continue
            elif not verified_recipient(recipient_email, db):
                transition_vacancy_status(
                    db=db,
                    vacancy_id=vacancy.id,
                    target_status=VacancyStatus.application_prepared,
                )
                continue

            email = crewai_generate_email(vacancy=vacancy)
            orm_email = create_email(
                db=db,
                vacancy_id=vacancy.id,
                email_data=email,
                recipient=recipient_email,
                resume_path=orm_resume.path,
            )
            send_email(orm_email)
            transition_vacancy_status(
                db=db,
                vacancy_id=vacancy.id,
                target_status=VacancyStatus.applied,
            )


if __name__ == "__main__":
    main()
