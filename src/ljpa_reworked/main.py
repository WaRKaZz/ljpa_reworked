import argparse
import logging
import os
import time
import uuid

from ljpa_reworked.config import HARNESS_API_URL, RESOURCES_DIR
from ljpa_reworked.crew_workflow import (
    crewai_evaluate_vacancy,
    crewai_generate_resume,
)
from ljpa_reworked.database import SessionLocal
from ljpa_reworked.models.crewai_pydantic_models import BasicEvaluationCrewAI
from ljpa_reworked.models.database_models import BasicEvaluation, Resume, Vacancy
from ljpa_reworked.models.enums import VacancyStatus
from ljpa_reworked.operations import (
    confirm_url_application_submitted,
    create_evaluation,
    get_resume_by_vacancy,
    get_unrated_vacancies,
    reconstruct_resume_crewai,
    transition_vacancy_status,
)
from ljpa_reworked.operations.evaluation_ops import build_ranked_submission_queue
from ljpa_reworked.services.harness_runner import (
    get_gemini_quota_remaining,
    harness_submit,
    run_linkedin_harness,
)
from ljpa_reworked.services.jobspy import JobSpyIntegrationService
from ljpa_reworked.services.rendercv_helper import render_resume_crewai_to_pdf
from ljpa_reworked.workflow import save_resume

logger = logging.getLogger(__name__)

SUBMISSION_LIMIT = 5
SUBMISSION_DELAY_SECONDS = 3 * 60 * 60
MINIMUM_GEMINI_5H_REMAINING = 0.07
SUBMIT_PROMPT_FILE = "/app/prompts/harness_submit.md"
SUBMIT_TIMEOUT = "4h"


def process_unevaluated_vacancies(db) -> None:
    """Evaluate new vacancies once, then backfill missing resumes for passing matches."""
    for vacancy in get_unrated_vacancies(db):
        evaluation = crewai_evaluate_vacancy(vacancy=vacancy)
        create_evaluation(db=db, vacancy_id=vacancy.id, evaluation_data=evaluation)
        if evaluation.rating < 50:
            vacancy.deleted = True
            db.commit()

    missing_resumes = (
        db.query(Vacancy, BasicEvaluation)
        .join(BasicEvaluation, BasicEvaluation.vacancy_id == Vacancy.id)
        .outerjoin(Resume, Resume.vacancy_id == Vacancy.id)
        .filter(
            Vacancy.deleted.is_(False),
            BasicEvaluation.rating >= 50,
            Resume.id.is_(None),
        )
        .all()
    )
    for vacancy, stored_evaluation in missing_resumes:
        evaluation = BasicEvaluationCrewAI(
            rating=stored_evaluation.rating,
            summary=stored_evaluation.summary or "",
        )
        resume = crewai_generate_resume(
            vacancy=vacancy, evaluation=evaluation
        )
        save_resume(resume, vacancy, db)
        transition_vacancy_status(
            db=db,
            vacancy_id=vacancy.id,
            target_status=VacancyStatus.application_prepared,
        )


def process_eligible_vacancies(db, vacancies) -> None:
    """Compatibility helper for callers that already selected unevaluated vacancies."""
    for vacancy in vacancies:
        if get_resume_by_vacancy(db, vacancy.id):
            continue
        evaluation = crewai_evaluate_vacancy(vacancy=vacancy)
        create_evaluation(db=db, vacancy_id=vacancy.id, evaluation_data=evaluation)
        if evaluation.rating < 50:
            vacancy.deleted = True
            db.commit()
            continue
        resume = crewai_generate_resume(
            vacancy=vacancy, evaluation=evaluation
        )
        save_resume(resume, vacancy, db)
        transition_vacancy_status(
            db=db,
            vacancy_id=vacancy.id,
            target_status=VacancyStatus.application_prepared,
        )


def submit_top_vacancies(db) -> int:
    """Submit at most five highest adjusted-score prepared URL applications."""
    submitted = 0
    for ranked in build_ranked_submission_queue(db)[:SUBMISSION_LIMIT]:
        remaining = get_gemini_quota_remaining(HARNESS_API_URL)
        if remaining <= MINIMUM_GEMINI_5H_REMAINING:
            logger.warning(
                "Stopping submissions: Gemini five-hour quota is %.1f%% (limit %.1f%%).",
                remaining * 100,
                MINIMUM_GEMINI_5H_REMAINING * 100,
            )
            break
        vacancy = ranked.vacancy
        resume_orm = get_resume_by_vacancy(db, vacancy.id)
        if resume_orm is None:
            logger.error(
                "Vacancy %s is prepared without a stored resume; skipping.",
                vacancy.id,
            )
            continue
        if submitted:
            time.sleep(SUBMISSION_DELAY_SECONDS)

        resumes_dir = os.path.join(RESOURCES_DIR, "resumes")
        os.makedirs(resumes_dir, exist_ok=True)
        pdf_filename = f"temp_resume_{vacancy.id}_{uuid.uuid4().hex[:8]}.pdf"
        temp_pdf_path = os.path.join(resumes_dir, pdf_filename)
        harness_resume_path = f"/inputs/resources/resumes/{pdf_filename}"

        try:
            resume_crewai = reconstruct_resume_crewai(resume_orm)
            render_resume_crewai_to_pdf(resume_crewai, temp_pdf_path)
            result = harness_submit(
                vacancy_url=vacancy.submit_url,
                resume_path=harness_resume_path,
                prompt_file=SUBMIT_PROMPT_FILE,
                timeout=SUBMIT_TIMEOUT,
                api_url=HARNESS_API_URL,
            )
            if result == 0:
                confirm_url_application_submitted(db=db, vacancy_id=vacancy.id)
            else:
                transition_vacancy_status(
                    db=db,
                    vacancy_id=vacancy.id,
                    target_status=VacancyStatus.application_error,
                )
                if os.path.exists(temp_pdf_path):
                    try:
                        os.remove(temp_pdf_path)
                    except OSError:
                        pass
        except Exception as exc:
            logger.error(
                "Application submission error for vacancy %s: %s", vacancy.id, exc
            )
            transition_vacancy_status(
                db=db,
                vacancy_id=vacancy.id,
                target_status=VacancyStatus.application_error,
            )
            if os.path.exists(temp_pdf_path):
                try:
                    os.remove(temp_pdf_path)
                except OSError:
                    pass
        submitted += 1
    return 0


def main(*, resume_only: bool = False, submit: bool = False) -> int:
    logger.info("=== STARTING SEQUENTIAL AGENTIC PIPELINE ===")
    if not resume_only:
        logger.info("[Step 1/4] Running LinkedIn Post Vacancy Collector...")
        run_linkedin_harness(api_url=HARNESS_API_URL)
        logger.info("[Step 2/4] Searching JobSpy vacancies...")
        try:
            JobSpyIntegrationService().run()
        except Exception as exc:
            logger.error("JobSpy search warning: %s", exc)
    else:
        logger.info("[Resume-only] Skipping LinkedIn harness and JobSpy discovery.")

    with SessionLocal() as db:
        logger.info(
            "[Step 3/4] Evaluating unreviewed vacancies and creating resumes..."
        )
        process_unevaluated_vacancies(db)
        if submit:
            logger.info(
                "[Step 4/4] Submitting up to %s top-ranked vacancies...",
                SUBMISSION_LIMIT,
            )
            return submit_top_vacancies(db)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--resume-only",
        action="store_true",
        help="Process saved vacancies without LinkedIn or JobSpy discovery.",
    )
    parser.add_argument(
        "--submit",
        action="store_true",
        help="Submit up to five ranked prepared URL vacancies, three hours apart.",
    )
    args = parser.parse_args()
    raise SystemExit(main(resume_only=args.resume_only, submit=args.submit))
