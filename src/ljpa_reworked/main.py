import argparse
import logging
import os
import time
from datetime import datetime

from ljpa_reworked.config import HARNESS_API_URL, RESOURCES_DIR
from ljpa_reworked.crew_workflow import (
    crewai_evaluate_vacancy,
    crewai_generate_resume,  # noqa: F401
    crewai_generate_resume_with_retry,
    crewai_review_submission_result,
)
from ljpa_reworked.database import SessionLocal, init_db
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
    harness_save_site_skill,
    harness_submit,
    run_linkedin_harness,
)
from ljpa_reworked.services.jobspy import JobSpyIntegrationService
from ljpa_reworked.services.rendercv_helper import (
    render_resume_crewai_to_pdf,
)
from ljpa_reworked.services.telegram import Telegram
from ljpa_reworked.workflow import persist_prepared_resume, save_resume  # noqa: F401

logger = logging.getLogger(__name__)

SUBMISSION_LIMIT = 5
SUBMISSION_DELAY_SECONDS = 3 * 60 * 60
MINIMUM_GEMINI_5H_REMAINING = 0.07
SUBMIT_PROMPT_FILE = "/app/prompts/harness_submit.md"
SUBMIT_TIMEOUT = "4h"
SUBMISSION_RESUMES_DIR = os.path.join(RESOURCES_DIR, "resumes")


def evaluate_unrated_vacancies(db) -> int:
    """Evaluate new unrated vacancies once and mark unsuitable ones deleted."""
    count = 0
    for vacancy in get_unrated_vacancies(db):
        evaluation = crewai_evaluate_vacancy(vacancy=vacancy)
        create_evaluation(db=db, vacancy_id=vacancy.id, evaluation_data=evaluation)
        if evaluation.rating < 50:
            vacancy.deleted = True
            db.commit()
        count += 1
    return count


def generate_missing_resumes(db) -> int:
    """Generate tailored resumes for evaluated suitable vacancies missing resumes."""
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
    count = 0
    for vacancy, stored_evaluation in missing_resumes:
        evaluation = BasicEvaluationCrewAI(
            rating=stored_evaluation.rating,
            summary=stored_evaluation.summary or "",
        )
        resume, temp_pdf_path = crewai_generate_resume_with_retry(
            vacancy=vacancy, evaluation=evaluation
        )
        persist_prepared_resume(resume, vacancy, db, temp_pdf_path)
        count += 1
    return count


def process_unevaluated_vacancies(db) -> None:
    """Compatibility helper: evaluate new vacancies and backfill missing resumes."""
    evaluate_unrated_vacancies(db)
    generate_missing_resumes(db)


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
        resume, temp_pdf_path = crewai_generate_resume_with_retry(
            vacancy=vacancy, evaluation=evaluation
        )
        persist_prepared_resume(resume, vacancy, db, temp_pdf_path)


def submit_top_vacancies(db) -> int:
    """Submit up to five prepared URL applications using their validated PDFs."""
    submitted = 0
    for ranked in build_ranked_submission_queue(db)[:SUBMISSION_LIMIT]:
        if get_gemini_quota_remaining(HARNESS_API_URL) <= MINIMUM_GEMINI_5H_REMAINING:
            logger.info(
                "Gemini quota remaining (<= %s) reached limit, pausing submissions.",
                MINIMUM_GEMINI_5H_REMAINING,
            )
            break
        vacancy = ranked.vacancy
        resume_orm = get_resume_by_vacancy(db, vacancy.id)
        if resume_orm is None:
            logger.warning(
                "No structured resume found for vacancy %s, marking as application_error.",
                vacancy.id,
            )
            transition_vacancy_status(db, vacancy.id, VacancyStatus.application_error)
            continue

        pdf_path = (
            os.path.join(SUBMISSION_RESUMES_DIR, resume_orm.path)
            if resume_orm.path
            else None
        )
        if not pdf_path or not os.path.isfile(pdf_path):
            try:
                os.makedirs(SUBMISSION_RESUMES_DIR, exist_ok=True)
                filename = f"resume_{vacancy.id}.pdf"
                target_pdf_path = os.path.join(SUBMISSION_RESUMES_DIR, filename)
                resume_crewai = reconstruct_resume_crewai(resume_orm)
                render_resume_crewai_to_pdf(resume_crewai, target_pdf_path)
                resume_orm.path = filename
                resume_orm.rendered_at = datetime.now()
                db.commit()
                pdf_path = target_pdf_path
                logger.info(
                    "Rendered on-demand resume PDF for vacancy %s at %s",
                    vacancy.id,
                    target_pdf_path,
                )
            except Exception as exc:
                logger.error(
                    "Failed to render resume PDF on-demand for vacancy %s: %s",
                    vacancy.id,
                    exc,
                )
                transition_vacancy_status(
                    db, vacancy.id, VacancyStatus.application_error
                )
                continue

        if submitted:
            time.sleep(SUBMISSION_DELAY_SECONDS)
        try:
            logger.info(
                "Submitting vacancy %s (%s) via harness...",
                vacancy.id,
                vacancy.title,
            )
            result = harness_submit(
                vacancy_url=vacancy.submit_url,
                resume_path=f"/inputs/resources/resumes/{resume_orm.path}",
                prompt_file=SUBMIT_PROMPT_FILE,
                timeout=SUBMIT_TIMEOUT,
                api_url=HARNESS_API_URL,
            )
            tail_lines = getattr(result, "tail_lines", [])
            if not tail_lines:
                logger.warning(
                    "No stream evidence received for vacancy %s",
                    vacancy.id,
                )
                transition_vacancy_status(
                    db, vacancy.id, VacancyStatus.application_error
                )
                try:
                    Telegram().send_message(
                        f"Application submission failed for vacancy {vacancy.id}: no stream evidence received."
                    )
                except Exception as telegram_exc:
                    logger.error(
                        "Failed to send Telegram submission error notification: %s",
                        telegram_exc,
                    )
            else:
                review = crewai_review_submission_result(tail_lines)
                if review.decision == "error":
                    err_desc = (
                        review.error_description or "Submission review failed"
                    ).strip()
                    logger.warning(
                        "Submission review rejected vacancy %s: %s",
                        vacancy.id,
                        err_desc,
                    )
                    transition_vacancy_status(
                        db, vacancy.id, VacancyStatus.application_error
                    )
                    try:
                        Telegram().send_message(
                            f"Application review error for vacancy {vacancy.id}: {err_desc}"
                        )
                    except Exception as telegram_exc:
                        logger.error(
                            "Failed to send Telegram review error notification: %s",
                            telegram_exc,
                        )
                else:
                    confirm_url_application_submitted(db=db, vacancy_id=vacancy.id)
                    logger.info(
                        "Successfully submitted application for vacancy %s", vacancy.id
                    )
                    cid = getattr(result, "conversation_id", None)
                    if cid:
                        try:
                            harness_save_site_skill(
                                conversation_id=cid,
                                prompt_file="/app/prompts/harness_save_site_skill.md",
                                timeout="30m",
                                api_url=HARNESS_API_URL,
                            )
                            logger.info(
                                "Successfully completed site skill saving for vacancy %s",
                                vacancy.id,
                            )
                        except Exception as skill_exc:
                            logger.error(
                                "Skill saving failed for vacancy %s: %s",
                                vacancy.id,
                                skill_exc,
                            )
                            try:
                                Telegram().send_message(
                                    f"Skill saving failed for vacancy {vacancy.id} (conversation {cid})."
                                )
                            except Exception as telegram_exc:
                                logger.error(
                                    "Failed to send Telegram skill save notification: %s",
                                    telegram_exc,
                                )
        except Exception as exc:
            logger.error(
                "Application submission error for vacancy %s: %s", vacancy.id, exc
            )
            transition_vacancy_status(db, vacancy.id, VacancyStatus.application_error)
        submitted += 1
    return 0



def main(
    mode: str | None = None,
    *,
    resume_only: bool = False,
    submit: bool = False,
) -> int:
    init_db()

    # Determine effective mode
    if mode is None:
        if resume_only:
            mode = "process" if submit else "process_no_submit"
        else:
            mode = "full" if submit else "full"

    logger.info("=== STARTING AGENTIC PIPELINE (MODE: %s) ===", mode.upper())

    # Step 1 & 2: Discovery
    if mode in ("full", "collect"):
        logger.info("[Step 1] Running LinkedIn Post Vacancy Collector...")
        run_linkedin_harness(api_url=HARNESS_API_URL)
        logger.info("[Step 2] Searching JobSpy vacancies...")
        try:
            JobSpyIntegrationService().run()
        except Exception as exc:
            logger.error("JobSpy search warning: %s", exc)
    else:
        logger.info("[Skip Searcher] Skipping LinkedIn harness and JobSpy discovery.")

    with SessionLocal() as db:
        if mode == "collect":
            logger.info("[Step 3] Evaluating unrated vacancies in database...")
            evaluate_unrated_vacancies(db)
            logger.info(
                "[Mode: Collect] Completed discovery and evaluation. Skipping resume generation and submission."
            )
            return 0

        logger.info("[Step 3] Evaluating unreviewed vacancies and creating resumes...")
        process_unevaluated_vacancies(db)

        if mode == "process_no_submit":
            logger.info("[Resume-only without submit] Skipping submissions.")
            return 0

        # Step 4: Submission
        logger.info(
            "[Step 4] Submitting up to %s top-ranked vacancies...",
            SUBMISSION_LIMIT,
        )
        return submit_top_vacancies(db)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="LinkedIn Job Processing Automation (LJPA)"
    )
    parser.add_argument(
        "--mode",
        choices=["full", "collect", "process"],
        default="full",
        help="Pipeline execution mode: 'full' (all stages), 'collect' (discovery + evaluation only), 'process' (resume generation + auto-submission on existing vacancies).",
    )
    parser.add_argument(
        "--resume-only",
        action="store_true",
        help="Process saved vacancies without LinkedIn or JobSpy discovery.",
    )
    parser.add_argument(
        "--submit",
        action="store_true",
        help="Submit up to five ranked prepared URL vacancies.",
    )
    args = parser.parse_args()

    if args.resume_only:
        mode_val = "process" if args.submit else "process_no_submit"
    else:
        mode_val = args.mode

    raise SystemExit(main(mode=mode_val, submit=args.submit))
