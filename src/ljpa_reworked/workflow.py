from __future__ import annotations

import logging
import os
import re
import shutil
from datetime import datetime, timedelta
from os import path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from ljpa_reworked.models.crewai_pydantic_models import (
        ResumeCrewAI,
        VacancyCrewAI,
    )
    from ljpa_reworked.models.database_models import (
        Email,
        LinkedinPost,
        Resume,
        Vacancy,
    )

from ljpa_reworked.config import (
    CV_FILE_NAME,
    RESOURCES_DIR,
    SCREENSHOTS_DIR,
    SMTP_EMAIL,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_SERVER,
)
from ljpa_reworked.crew_workflow import crewai_process_linkedin_post
from ljpa_reworked.models.database_models import DataSource
from ljpa_reworked.operations import (
    create_linkedin_post,
    create_resume,
    create_vacancy,
    get_duplicate_post,
    get_emails_by_recipient,
    link_post_to_vacancy,
    mark_linkedin_post_as_processed,
    mark_vacancy_as_sent,
)
from ljpa_reworked.services.linkedin_scraper import LinkedInScraper
from ljpa_reworked.services.resume_generator import ResumeGenerator
from ljpa_reworked.services.smtp_client import SMTPClient
from ljpa_reworked.services.telegram import Telegram

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
SIMILARITY_THRESHOLD = 92


def _save_screenshot(screenshot_data: bytes) -> str:
    """Saves a screenshot to the screenshots directory and returns the filename."""
    screenshot_name = f"{datetime.now().timestamp()}.png"
    screenshot_path = path.join(SCREENSHOTS_DIR, screenshot_name)
    with open(screenshot_path, "wb") as f:
        f.write(screenshot_data)
    return screenshot_name


def _handle_raw_post(db: Session, raw_post) -> LinkedinPost | None:
    """Handles a single raw post from LinkedIn scraper.

    Checks for duplicates, and creates a new post if it's not a duplicate.
    """
    duplicate_post = get_duplicate_post(
        db, raw_post.text, threshold=SIMILARITY_THRESHOLD
    )

    if duplicate_post:
        if duplicate_post.processed:
            logger.info(
                "Skipping post due to similarity with an existing and processed post."
            )
            return None
        # Reprocess if not processed
        logger.info(f"Post {duplicate_post.id} will be reprocessed.")
        return duplicate_post

    screenshot_name = _save_screenshot(raw_post.screenshot)
    return create_linkedin_post(
        db=db, text=raw_post.text, screenshot_path=screenshot_name, url=raw_post.url
    )


def get_linkedin_posts(db: Session) -> list[LinkedinPost]:
    """Scrapes LinkedIn for job posts and saves them to the database."""
    raw_posts = LinkedInScraper().get_vacancies()
    if not raw_posts:
        logger.info("No new LinkedIn posts found.")
        return []

    posts = []
    for raw_post in raw_posts:
        post = _handle_raw_post(db, raw_post)
        if post:
            posts.append(post)

    logger.info(f"Found and saved {len(posts)} new LinkedIn posts.")
    return posts


def _validate_vacancy_data(vacancy: VacancyCrewAI) -> None:
    """Validates that the vacancy data from CrewAI is complete."""
    if vacancy.post_id is None:
        raise ValueError("Vacancy must have a post_id.")
    if not vacancy.title:
        raise ValueError(
            f"Vacancy title is missing for post with id: {vacancy.post_id}"
        )
    if not vacancy.text:
        raise ValueError(f"Vacancy text is missing for post with id: {vacancy.post_id}")
    if not vacancy.credentials:
        raise ValueError(
            f"Vacancy credentials are missing for post with id: {vacancy.post_id}"
        )


def save_vacancies(vacancies: list[VacancyCrewAI], db: Session) -> None:
    """Saves vacancies to the database."""
    for vacancy in vacancies:
        _validate_vacancy_data(vacancy)
        orm_vacancy = create_vacancy(
            db=db, vacancy_data=vacancy, source=DataSource.linkedin
        )
        # post_id is checked in _validate_vacancy_data
        post_id = cast(int, vacancy.post_id)
        link_post_to_vacancy(db=db, post_id=post_id, vacancy_id=orm_vacancy.id)
    logger.info(f"Saved {len(vacancies)} vacancies.")


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
    resume_name = f"{datetime.now().timestamp()}.pdf"
    orm_resume = create_resume(
        db=db,
        vacancy_id=vacancy.id,
        resume_data=resume,
        path=resume_name,
    )

    resume_dir = os.path.join(RESOURCES_DIR, "resumes")
    os.makedirs(resume_dir, exist_ok=True)

    resume_path = os.path.join(resume_dir, resume_name)
    ResumeGenerator(orm_resume.to_dict()).generate(resume_path)
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
    if not vacancy.linkedin_posts:
        logger.warning(
            f"Vacancy {vacancy.id} has no associated LinkedIn post to send to Telegram."
        )
        return

    linkedin_post = vacancy.linkedin_posts

    if not linkedin_post.screenshot_path:
        logger.error(
            f"Vacancy {vacancy.id} has a LinkedIn post but no screenshot path."
        )
        return

    if not vacancy.basic_evaluation:
        logger.error(f"Vacancy {vacancy.id} has no basic evaluation.")
        return

    screenshot_path = path.join(SCREENSHOTS_DIR, linkedin_post.screenshot_path)
    if not path.exists(screenshot_path):
        logger.error(
            f"Screenshot not found for vacancy {vacancy.id} at {screenshot_path}"
        )
        return

    text = (
        f"Title: {vacancy.title}\n\n"
        f"URL: {vacancy.url}\n\n"
        f"TO: {vacancy.credentials}\n\n"
        f"Rating: {vacancy.basic_evaluation.rating}\n\n"
        f"{vacancy.text}"
    )

    try:
        Telegram().send_image(image_path=screenshot_path, caption=text[:4000])
        mark_vacancy_as_sent(db=db, vacancy_id=vacancy.id)
        logger.info(f"Sent vacancy {vacancy.id} to Telegram.")
    except Exception as e:
        logger.error(f"Failed to send Telegram post for vacancy {vacancy.id}: {e}")
        raise


def process_linkedin_posts(
    posts: list[LinkedinPost], db: Session
) -> list[VacancyCrewAI]:
    """Processes a list of LinkedIn posts to extract vacancy information."""
    vacancies = []
    for post in posts:
        mark_linkedin_post_as_processed(db, post.id)
        processed_vacancy = crewai_process_linkedin_post(post, db)
        if processed_vacancy:
            vacancies.append(processed_vacancy)

    logger.info(f"Processed {len(posts)} posts, yielding {len(vacancies)} vacancies.")
    return vacancies
