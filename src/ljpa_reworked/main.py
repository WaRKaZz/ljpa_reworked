#!/usr/bin/env python
from typing import cast

from ljpa_reworked.crew_workflow import (
    crewai_evaluate_vacancy,
    crewai_generate_email,
    crewai_generate_resume,
)
from ljpa_reworked.database import SessionLocal
from ljpa_reworked.operations import (
    create_email,
    create_evaluation,
    get_eligble_vacancies,
    update_vacancy,
)
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


from ljpa_reworked.services.harness_jobspy import fetch_and_store_jobs
from ljpa_reworked.services.harness_posts_scraper import run_agy_harness_1, run_posts_scraper

logger = logging.getLogger(__name__)


def main():
    logger.info("=== STARTING SEQUENTIAL AGENTIC PIPELINE ===")

    # Step 1: Execute Harness 1 (AGY LinkedIn Posts Agent in container) synchronously
    logger.info("[Step 1/4] Executing Harness 1 (LinkedIn Posts Search Agent)...")
    try:
        run_agy_harness_1()
    except Exception as e:
        logger.warning(f"Container agy harness execution warning: {e}. Running fallback synchronous scraper...")
        import asyncio
        asyncio.run(run_posts_scraper(max_posts=10))

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
                update_vacancy(db=db, vacancy_id=vacancy.id, processed=True)
                continue

            resume = crewai_generate_resume(vacancy=vacancy, evaluation=evaluation)
            orm_resume = save_resume(resume, vacancy, db)

            recipient_email = extract_email(vacancy_credentials)
            if not recipient_email:
                send_telegram_post(vacancy=vacancy, db=db)
                update_vacancy(db=db, vacancy_id=vacancy.id, processed=True)
                continue
            elif not verified_recipient(recipient_email, db):
                update_vacancy(db=db, vacancy_id=vacancy.id, processed=True)
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
            update_vacancy(db=db, vacancy_id=vacancy.id, processed=True)


if __name__ == "__main__":
    main()
