#!/usr/bin/env python
import logging
import os

from ljpa_reworked.config import RESOURCES_DIR
from ljpa_reworked.crew_workflow import (
    crewai_evaluate_vacancy,
    crewai_generate_email,
    crewai_generate_resume_with_retry,
)
from ljpa_reworked.database import SessionLocal
from ljpa_reworked.models.enums import VacancyStatus
from ljpa_reworked.operations import (
    confirm_application_submitted,
    confirm_email_application_submitted,
    create_email,
    create_evaluation,
    get_eligble_vacancies,
    get_eligible_url_vacancies,
    transition_vacancy_status,
)
from ljpa_reworked.services.harness_runner import (
    harness_submit,
    run_linkedin_harness,
)
from ljpa_reworked.services.jobspy import JobSpyIntegrationService
from ljpa_reworked.workflow import (
    extract_email,
    save_resume,
    send_email,
    verified_recipient,
)

logger = logging.getLogger(__name__)


def process_eligible_vacancies(db, vacancies):
    eligible_url_vacancies = get_eligible_url_vacancies(
        db=db, limit=20, max_age_days=60
    )
    eligible_url_ids = {v.id for v in eligible_url_vacancies}

    for vacancy in vacancies:
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

        resume, temp_pdf_path = crewai_generate_resume_with_retry(
            vacancy=vacancy, evaluation=evaluation
        )
        orm_resume = save_resume(
            resume, vacancy, db, temp_pdf_path=temp_pdf_path
        )

        recipient_email = vacancy.submit_email or (
            extract_email(vacancy.submit_url or "") if vacancy.submit_url else None
        )

        if recipient_email and verified_recipient(recipient_email, db):
            email = crewai_generate_email(vacancy=vacancy)
            orm_email = create_email(
                db=db,
                vacancy_id=vacancy.id,
                email_data=email,
                recipient=recipient_email,
                resume_path=orm_resume.path,
            )
            send_email(orm_email)
            confirm_email_application_submitted(
                db=db,
                vacancy_id=vacancy.id,
            )
        else:
            transition_vacancy_status(
                db=db,
                vacancy_id=vacancy.id,
                target_status=VacancyStatus.application_prepared,
            )

        if (
            vacancy.submit_url
            and vacancy.id in eligible_url_ids
            and vacancy.status != VacancyStatus.applied
        ):
            pdf_path = os.path.join(RESOURCES_DIR, "resumes", orm_resume.path)
            res = harness_submit(vacancy_url=vacancy.submit_url, resume_path=pdf_path)
            if res == 0:
                confirm_application_submitted(
                    db=db,
                    vacancy_id=vacancy.id,
                )
            elif res == 1:
                transition_vacancy_status(
                    db=db,
                    vacancy_id=vacancy.id,
                    target_status=VacancyStatus.application_error,
                )




def main():
    logger.info("=== STARTING SEQUENTIAL AGENTIC PIPELINE ===")

    # Step 1: Run LinkedIn Post Vacancy Collector.
    logger.info("[Step 1/4] Running LinkedIn Post Vacancy Collector...")
    run_linkedin_harness()

    # Step 2: Search JobSpy and store vacancies before review.
    logger.info("[Step 2/4] Searching JobSpy vacancies...")
    try:
        JobSpyIntegrationService().run()
    except Exception as exc:
        logger.error("JobSpy search warning: %s", exc)

    # Step 3: Process and Evaluate Vacancies Sequentially
    logger.info("[Step 3/4] Evaluating candidate vacancies sequentially...")
    with SessionLocal() as db:
        vacancies = get_eligble_vacancies(db=db)
        logger.info("Found %d eligible vacancies for evaluation.", len(vacancies))
        process_eligible_vacancies(db, vacancies)


if __name__ == "__main__":
    main()
