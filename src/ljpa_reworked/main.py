import argparse
import logging
import os
import sys
from datetime import datetime

from sqlalchemy import func

from ljpa_reworked.config import HARNESS_API_URL, MINIMUM_SCORE, RESOURCES_DIR
from ljpa_reworked.crew_workflow import (
    crewai_evaluate_vacancy,
    crewai_generate_email,
    crewai_generate_resume,  # noqa: F401
    crewai_generate_resume_with_retry,
    crewai_review_submission_result,
)
from ljpa_reworked.database import SessionLocal, init_db
from ljpa_reworked.models.crewai_pydantic_models import BasicEvaluationCrewAI
from ljpa_reworked.models.database_models import BasicEvaluation, Resume, Vacancy
from ljpa_reworked.models.enums import VacancyStatus
from ljpa_reworked.operations import (
    confirm_email_application_submitted,
    confirm_url_application_submitted,
    create_email,
    create_evaluation,
    extract_primary_email,
    get_resume_by_vacancy,
    get_unrated_vacancies,
    has_recent_sent_email_to_recipient,
    mark_email_sent,
    reconstruct_resume_crewai,
    transition_vacancy_status,
)
from ljpa_reworked.operations.evaluation_ops import (
    build_ranked_email_submission_queue,
    build_ranked_submission_queue,
)
from ljpa_reworked.services.chatgpt_gdrive import ChatGPTGDriveService
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
from ljpa_reworked.workflow import (
    persist_prepared_resume,
    save_resume,  # noqa: F401
    send_email,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

SUBMISSION_LIMIT = 5
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
        if evaluation.rating < MINIMUM_SCORE:
            vacancy.deleted = True
            db.commit()
        count += 1
    return count


def generate_missing_resumes(db) -> int:
    """Generate tailored resumes for evaluated suitable vacancies missing resumes."""
    latest_evaluation_id = (
        db.query(BasicEvaluation.vacancy_id, func.max(BasicEvaluation.id).label("id"))
        .group_by(BasicEvaluation.vacancy_id)
        .subquery()
    )
    missing_resumes = (
        db.query(Vacancy, BasicEvaluation)
        .join(latest_evaluation_id, latest_evaluation_id.c.vacancy_id == Vacancy.id)
        .join(BasicEvaluation, BasicEvaluation.id == latest_evaluation_id.c.id)
        .outerjoin(Resume, Resume.vacancy_id == Vacancy.id)
        .filter(
            Vacancy.deleted.is_(False),
            Vacancy.applied_at.is_(None),
            Vacancy.status.notin_(
                [
                    VacancyStatus.submitted_via_email,
                    VacancyStatus.submitted_via_url,
                    VacancyStatus.submitted_via_all,
                    VacancyStatus.withdrawn,
                    VacancyStatus.expired,
                    VacancyStatus.archived,
                    VacancyStatus.rejected,
                    VacancyStatus.application_error,
                    VacancyStatus.review_error,
                ]
            ),
            Resume.id.is_(None),
        )
        .all()
    )
    count = 0
    for vacancy, stored_evaluation in missing_resumes:
        if get_resume_by_vacancy(db, vacancy.id):
            continue
        visa_prob = getattr(stored_evaluation, "visa_probability", 100)
        if visa_prob is None:
            visa_prob = 100
        score = stored_evaluation.rating - (100.0 - visa_prob) / 2.2
        if score < MINIMUM_SCORE:
            continue
        evaluation = BasicEvaluationCrewAI(
            rating=stored_evaluation.rating,
            visa_probability=visa_prob,
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
        visa_prob = getattr(evaluation, "visa_probability", 100)
        if visa_prob is None:
            visa_prob = 100
        score = evaluation.rating - (100.0 - visa_prob) / 2.2
        if score < MINIMUM_SCORE:
            continue
        resume, temp_pdf_path = crewai_generate_resume_with_retry(
            vacancy=vacancy, evaluation=evaluation
        )
        persist_prepared_resume(resume, vacancy, db, temp_pdf_path)


def submit_top_email_vacancies(db, limit: int | None = None) -> int:
    """Submit prepared email applications using tailored cover letters and PDFs."""
    submitted = 0
    queue = build_ranked_email_submission_queue(db)
    if limit is not None:
        queue = queue[:limit]
    for ranked in queue:
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

        recipient = extract_primary_email(vacancy.submit_email) or vacancy.submit_email
        if not recipient:
            logger.warning(
                "No valid recipient email for vacancy %s, marking as application_error.",
                vacancy.id,
            )
            transition_vacancy_status(db, vacancy.id, VacancyStatus.application_error)
            continue

        if has_recent_sent_email_to_recipient(db, recipient=recipient, days=30):
            logger.info(
                "Skipping vacancy %s: email already sent to %s within the last 30 days. Archiving vacancy.",
                vacancy.id,
                recipient,
            )
            transition_vacancy_status(db, vacancy.id, VacancyStatus.archived)
            continue

        try:
            logger.info(
                "Generating tailored application email for vacancy %s (%s)...",
                vacancy.id,
                vacancy.title,
            )
            email_crewai = crewai_generate_email(vacancy=vacancy)
            email_record = create_email(
                db=db,
                vacancy_id=vacancy.id,
                email_data=email_crewai,
                recipient=recipient,
                resume_path=resume_orm.path,
            )
            logger.info("Sending application email to %s...", recipient)
            send_email(email_record)
            mark_email_sent(db, email_record.id)
            confirm_email_application_submitted(db=db, vacancy_id=vacancy.id)
            logger.info(
                "Successfully sent email application for vacancy %s", vacancy.id
            )
            submitted += 1
        except Exception as exc:
            logger.error(
                "Email application submission error for vacancy %s: %s",
                vacancy.id,
                exc,
            )
            transition_vacancy_status(db, vacancy.id, VacancyStatus.application_error)
            try:
                Telegram().send_message(
                    f"Email application submission failed for vacancy {vacancy.id}: {exc}"
                )
            except Exception as telegram_exc:
                logger.error(
                    "Failed to send Telegram email submission error notification: %s",
                    telegram_exc,
                )

    return submitted


def submit_top_vacancies(db, limit: int | None = None) -> int:
    """Submit prepared URL applications using their validated PDFs as long as quota allows."""
    submitted = 0
    queue = build_ranked_submission_queue(db)
    if limit is not None:
        queue = queue[:limit]
    for ranked in queue:
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
                                    f"Skill saving failed for vacancy {vacancy.id} (conversation {cid}): {skill_exc}"
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


def main(mode: str = "collect", dry_run: bool = False) -> int:
    init_db()

    normalized_mode = mode.lower().replace("_", "-")
    logger.info(
        "=== STARTING AGENTIC PIPELINE (MODE: %s, DRY_RUN: %s) ===",
        normalized_mode.upper(),
        dry_run,
    )

    if normalized_mode in ("collect", "collect-all"):
        logger.info("[Step 1] Running LinkedIn Post Vacancy Collector...")
        run_linkedin_harness(api_url=HARNESS_API_URL)
        logger.info("[Step 2] Searching JobSpy vacancies...")
        try:
            JobSpyIntegrationService().run()
        except Exception as exc:
            logger.error("JobSpy search warning: %s", exc)

        with SessionLocal() as db:
            logger.info("[Step 3] Evaluating unrated vacancies in database...")
            evaluate_unrated_vacancies(db)
            logger.info("[Mode: collect] Completed discovery and evaluation.")
            return 0

    if normalized_mode == "collect-chatgpt":
        with SessionLocal() as db:
            logger.info(
                "[Step 1] Fetching and synchronizing vacancies from Google Drive..."
            )
            service = ChatGPTGDriveService(dry_run=dry_run)
            added, skipped = service.run(db)
            if not dry_run:
                logger.info("[Step 2] Evaluating unrated vacancies in database...")
                evaluate_unrated_vacancies(db)
            else:
                logger.info("[Dry Run] Skipped evaluation of vacancies.")
            logger.info(
                "[Mode: collect-chatgpt] Completed. Added: %d, Skipped: %d.",
                added,
                skipped,
            )
            return 0

    if normalized_mode == "collect-harness":
        logger.info("[Step 1] Running LinkedIn Post Vacancy Collector via Harness...")
        run_linkedin_harness(api_url=HARNESS_API_URL)
        with SessionLocal() as db:
            logger.info("[Step 2] Evaluating unrated vacancies in database...")
            evaluate_unrated_vacancies(db)
            logger.info("[Mode: collect-harness] Completed discovery and evaluation.")
            return 0

    if normalized_mode == "collect-jobspy":
        logger.info("[Step 1] Searching JobSpy vacancies...")
        try:
            JobSpyIntegrationService().run()
        except Exception as exc:
            logger.error("JobSpy search warning: %s", exc)

        with SessionLocal() as db:
            logger.info("[Step 2] Evaluating unrated vacancies in database...")
            evaluate_unrated_vacancies(db)
            logger.info("[Mode: collect-jobspy] Completed discovery and evaluation.")
            return 0

    if normalized_mode in ("email-submit", "email-process"):
        with SessionLocal() as db:
            logger.info(
                "[Step 1] Evaluating unreviewed vacancies and creating resumes..."
            )
            process_unevaluated_vacancies(db)

            logger.info(
                "[Step 2] Submitting email applications until all score >= %s vacancies are processed...",
                MINIMUM_SCORE,
            )
            submit_top_email_vacancies(db, limit=None)
            return 0

    if normalized_mode in ("url-submit", "url-process"):
        with SessionLocal() as db:
            logger.info(
                "[Step 1] Evaluating unreviewed vacancies and creating resumes..."
            )
            process_unevaluated_vacancies(db)

            logger.info(
                "[Step 2] Submitting URL applications while Gemini quota > 7%..."
            )
            submit_top_vacancies(db, limit=None)
            return 0

    logger.error("Unknown pipeline mode: %s", mode)
    return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="LinkedIn Job Processing Automation (LJPA)"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--collect-chatgpt",
        action="store_true",
        help="Fetch vacancies from Google Drive, validate, sync to DB, and evaluate fit.",
    )
    group.add_argument(
        "--collect-harness",
        action="store_true",
        help="Run LinkedIn Harness post scraper and evaluate new vacancies.",
    )
    group.add_argument(
        "--collect-jobspy",
        action="store_true",
        help="Search JobSpy LinkedIn/Indeed vacancies and evaluate new vacancies.",
    )
    group.add_argument(
        "--url-submit",
        action="store_true",
        help="Generate resumes and submit URL applications while Gemini quota > 7%%.",
    )
    group.add_argument(
        "--email-submit",
        action="store_true",
        help=f"Generate resumes and submit email applications for vacancies with score >= {MINIMUM_SCORE}.",
    )
    group.add_argument(
        "--mode",
        choices=[
            "collect-chatgpt",
            "collect-harness",
            "collect-jobspy",
            "url-submit",
            "email-submit",
            "collect_chatgpt",
            "collect_harness",
            "collect_jobspy",
            "url_submit",
            "email_submit",
        ],
        help="Alternative parameter to select pipeline execution mode.",
    )
    parser.add_argument(
        "positional_mode",
        nargs="?",
        default=None,
        choices=[
            "collect-chatgpt",
            "collect-harness",
            "collect-jobspy",
            "url-submit",
            "email-submit",
            "collect_chatgpt",
            "collect_harness",
            "collect_jobspy",
            "url_submit",
            "email_submit",
        ],
        help="Optional positional mode parameter.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate execution without modifying the database.",
    )

    args = parser.parse_args()

    selected_mode = None
    if args.collect_chatgpt:
        selected_mode = "collect-chatgpt"
    elif args.collect_harness:
        selected_mode = "collect-harness"
    elif args.collect_jobspy:
        selected_mode = "collect-jobspy"
    elif args.url_submit:
        selected_mode = "url-submit"
    elif args.email_submit:
        selected_mode = "email-submit"
    elif args.mode:
        selected_mode = args.mode
    elif args.positional_mode:
        selected_mode = args.positional_mode
    else:
        selected_mode = "collect-chatgpt"

    raise SystemExit(main(mode=selected_mode, dry_run=args.dry_run))
