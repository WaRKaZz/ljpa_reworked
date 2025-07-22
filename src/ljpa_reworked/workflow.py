import os
import re
import shutil
from datetime import datetime
from os import path
from typing import TYPE_CHECKING

from thefuzz import fuzz

from ljpa_reworked.config import (
    CV_FILE_NAME,
    RESOURCES_DIR,
    SCREENSHOTS_DIR,
    SMTP_EMAIL,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_SERVER,
)
from ljpa_reworked.models.database_models import DataSource
from ljpa_reworked.operations import (
    create_linkedin_post,
    create_resume,
    create_vacancy,
    get_all_linkedin_posts,
    get_emails_by_recipient,
    link_post_to_vacancy,
    mark_vacancy_as_sent,
)
from ljpa_reworked.services.linkedin_scraper import LinkedInScraper
from ljpa_reworked.services.resume_generator import ResumeGenerator
from ljpa_reworked.services.smtp_client import SMTPClient
from ljpa_reworked.services.telegram import Telegram

if TYPE_CHECKING:
    from ljpa_reworked.database import SessionLocal
    from ljpa_reworked.models.crewai_pydantic_models import (
        ResumeCrewAI,
    )
    from ljpa_reworked.models.database_models import Email, Resume, Vacancy
SIMILARITY_THRESHOLD = 92


def _is_duplicate(text: str, existing_texts: list[str]) -> bool:
    """Checks if a given text is a duplicate of any in a list of existing texts."""
    for existing_text in existing_texts:
        similarity = fuzz.token_set_ratio(text, existing_text)
        if similarity >= SIMILARITY_THRESHOLD:
            print(
                f"Skipping post due to {similarity}% similarity with an existing post."
            )
            return True
    return False


def _save_screenshot(screenshot_data: bytes) -> str:
    """Saves a screenshot to the screenshots directory and returns the filename."""
    screenshot_name = f"{datetime.now().timestamp()}.png"
    screenshot_path = path.join(SCREENSHOTS_DIR, screenshot_name)
    with open(screenshot_path, "wb") as f:
        f.write(screenshot_data)
    return screenshot_name


def get_linkedin_posts(db: "SessionLocal") -> list[dict]:
    raw_posts = LinkedInScraper().get_vacancies()
    if not raw_posts:
        return []

    posts = []
    recent_posts = get_all_linkedin_posts(db, limit=20)
    existing_texts = [post.text for post in recent_posts]

    for text, data in raw_posts.items():
        if _is_duplicate(text, existing_texts):
            continue

        screenshot_name = _save_screenshot(data[0])

        post = create_linkedin_post(
            db=db,
            text=text,
            screenshot_path=screenshot_name,
        )
        posts.append(post.to_dict())
        posts[-1]["url"] = data[1]
        existing_texts.append(text)
    return posts


def save_vacancies(vacancies, db: "SessionLocal") -> int:
    for vacancy in vacancies:
        orm_vacancy = create_vacancy(
            db=db, vacancy_data=vacancy, source=DataSource.linkedin
        )
        link_post_to_vacancy(db=db, post_id=vacancy.post_id, vacancy_id=orm_vacancy.id)


def extract_email(credentials: str) -> str | None:
    if not isinstance(credentials, str):
        return None

    email_regex = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    match = re.search(email_regex, credentials)
    return match.group(0) if match else None


def save_resume(
    resume: "ResumeCrewAI", vacancy: "Vacancy", db: "SessionLocal"
) -> "Resume":
    resume_name = f"{datetime.now().timestamp()}.pdf"
    orm_resume = create_resume(
        db=db,
        vacancy_id=vacancy.id,
        resume_data=resume,
        path=resume_name,
    )

    RESUME_DIR = os.path.join(RESOURCES_DIR, "resumes")

    if not os.path.exists(RESUME_DIR):
        os.makedirs(RESUME_DIR)

    resume_path = os.path.join(RESUME_DIR, resume_name)
    ResumeGenerator(orm_resume.to_dict()).generate(resume_path)
    return orm_resume


def _prepare_resume_for_sending(resume_path: str) -> str:
    """Copies the resume to a temporary location and returns the path."""
    full_resume_path = path.join(RESOURCES_DIR, "resumes", resume_path)
    temp_resume_path = f"/tmp/{CV_FILE_NAME}"

    if os.path.exists(temp_resume_path):
        os.remove(temp_resume_path)

    shutil.copy(full_resume_path, temp_resume_path)
    return temp_resume_path


def verified_recepient(email, db: "SessionLocal"):
    emails = get_emails_by_recipient(db, email)
    one_month_ago = datetime.now() - datetime.timedelta(month=1)
    for email in emails:
        given_date = datetime.datetime.strptime(email.created_at, "%Y-%m-%d %H:%M:%S")
        if given_date < one_month_ago:
            return False
    return True


def send_email(email: "Email") -> None:
    config = {
        "email": SMTP_EMAIL,
        "password": SMTP_PASSWORD,
        "smtp_server": SMTP_SERVER,
        "smtp_port": SMTP_PORT,
    }
    """Sends an email using the provided SMTP client."""
    attachment_path = _prepare_resume_for_sending(email.resume_path)

    with SMTPClient(config=config) as client:
        try:
            client.send_email(
                to=email.recipient,
                subject=email.subject,
                body=email.body,
                attachment=attachment_path,
            )
            print(f"Email successfully sent to {email.recipient}")
        except Exception as e:
            print(f"Failed to send email to {email.recipient}: {e}")


def send_telegram_post(vacancy: "Vacancy", db: "SessionLocal"):
    telegram = Telegram()
    screenshot_path = path.join(SCREENSHOTS_DIR, vacancy.linkedin_posts.screenshot_path)
    mark_vacancy_as_sent(db=db, vacancy_id=vacancy.id)
    text = f"Title: {vacancy.title}\n\nURL: {vacancy.url}\n\nTO: {vacancy.credentials}\n\nRating: {vacancy.basic_evaluation.rating}\n\n{vacancy.text}"
    telegram.send_image(image_path=screenshot_path, caption=text[:4000])
