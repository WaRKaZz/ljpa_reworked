from __future__ import annotations

import logging
import os
import re
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from os import path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from ljpa_reworked.models.crewai_pydantic_models import ResumeCrewAI
    from ljpa_reworked.models.database_models import (
        Email,
        Resume,
        Vacancy,
    )

from ljpa_reworked.config import (
    CV_FILE_NAME,
    RESOURCES_DIR,
    SMTP_EMAIL,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_SERVER,
)
from ljpa_reworked.operations import (
    create_resume,
    get_emails_by_recipient,
    mark_vacancy_as_sent,
)
from ljpa_reworked.services.rendercv_helper import render_resume_crewai_to_pdf
from ljpa_reworked.services.smtp_client import SMTPClient
from ljpa_reworked.services.telegram import Telegram

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def extract_email(credentials: str) -> str | None:
    """Extracts an email address from a string."""
    if not isinstance(credentials, str):
        raise TypeError("credentials must be a string.")

    email_regex = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    match = re.search(email_regex, credentials)
    if not match:
        return None
    return match.group(0)


def save_resume(resume: ResumeCrewAI, vacancy: Vacancy, db: Session) -> Resume:
    """Saves a generated resume to the database and filesystem."""
    resume_dir = os.path.join(RESOURCES_DIR, "resumes")
    os.makedirs(resume_dir, exist_ok=True)

    unique_id = uuid.uuid4().hex[:8]
    resume_name = f"resume_{vacancy.id}_{unique_id}.pdf"
    resume_path = os.path.join(resume_dir, resume_name)

    try:
        render_resume_crewai_to_pdf(resume, resume_path)
        if not os.path.exists(resume_path) or os.path.getsize(resume_path) == 0:
            raise RuntimeError(
                f"RenderCV failed to generate a non-empty PDF at {resume_path}"
            )
    except Exception:
        if os.path.exists(resume_path):
            try:
                os.remove(resume_path)
            except OSError:
                pass
        raise

    rendered_at = datetime.now(timezone.utc)

    try:
        orm_resume = create_resume(
            db=db,
            vacancy_id=vacancy.id,
            resume_data=resume,
            path=resume_name,
            rendered_at=rendered_at,
        )
    except Exception:
        if os.path.exists(resume_path):
            try:
                os.remove(resume_path)
            except OSError:
                pass
        raise

    logger.info(f"Saved resume {resume_name} for vacancy {vacancy.id}.")
    return orm_resume


def _prepare_resume_for_sending(resume_path: str) -> str:
    """Copies the resume to a temporary location for sending."""
    full_resume_path = path.join(RESOURCES_DIR, "resumes", resume_path)
    if not path.exists(full_resume_path):
        raise FileNotFoundError(f"Resume file not found at {full_resume_path}")

    temp_resume_path = f"/tmp/{CV_FILE_NAME}"
    shutil.copy(full_resume_path, temp_resume_path)
    return temp_resume_path


def verified_recipient(email_address: str, db: Session) -> bool:
    """Checks if an email has been sent to the recipient in the last 30 days."""
    emails = get_emails_by_recipient(db, email_address)
    one_month_ago = datetime.now() - timedelta(days=30)
    return not any(email.created_at > one_month_ago for email in emails)


def _get_smtp_config() -> dict:
    """Returns the SMTP configuration."""
    return {
        "email": SMTP_EMAIL,
        "password": SMTP_PASSWORD,
        "smtp_server": SMTP_SERVER,
        "smtp_port": SMTP_PORT,
    }


def send_email(email: Email) -> None:
    """Sends an email with the resume as an attachment."""
    if not email.body:
        raise ValueError(f"Email body for recipient {email.recipient} is empty.")
    if not email.resume_path:
        raise ValueError(f"Email for recipient {email.recipient} has no resume path.")

    attachment_path = _prepare_resume_for_sending(email.resume_path)
    config = _get_smtp_config()

    try:
        with SMTPClient(config=config) as client:
            client.send_email(
                to=email.recipient,
                subject=email.subject,
                body=email.body,
                attachment=attachment_path,
            )
        logger.info(f"Email successfully sent to {email.recipient}")
    except Exception as e:
        logger.error(f"Failed to send email to {email.recipient}: {e}")
        raise  # Re-raise the exception to be handled by the caller


def send_telegram_post(vacancy: Vacancy, db: Session) -> None:
    """Sends a post to Telegram if an email could not be sent."""
    if not vacancy.basic_evaluation:
        logger.error(f"Vacancy {vacancy.id} has no basic evaluation.")
        return

    text = (
        f"Title: {vacancy.title}\n\n"
        f"URL: {vacancy.submit_url or ''}\n\n"
        f"TO: {vacancy.submit_email or ''}\n\n"
        f"Rating: {vacancy.basic_evaluation.rating}\n\n"
        f"{vacancy.text}"
    )

    try:
        Telegram().send_message(message=text[:4000])
        mark_vacancy_as_sent(db=db, vacancy_id=vacancy.id)
        logger.info(f"Sent vacancy {vacancy.id} to Telegram.")
    except Exception as e:
        logger.error(f"Failed to send Telegram post for vacancy {vacancy.id}: {e}")
        raise
