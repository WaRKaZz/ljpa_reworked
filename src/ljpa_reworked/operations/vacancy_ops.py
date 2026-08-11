import logging
import re
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from ljpa_reworked.models.crewai_pydantic_models import VacancyCrewAI
from ljpa_reworked.models.crewai_pydantic_models import VisaStatus
from ljpa_reworked.models.database_models import DataSource, Vacancy
from ljpa_reworked.models.enums import VacancyStatus

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = {
    VacancyStatus.applied,
    VacancyStatus.withdrawn,
    VacancyStatus.expired,
    VacancyStatus.archived,
}

EMAIL_REGEX = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"


def _normalize_and_validate_contacts(
    submit_email: str | None,
    submit_url: str | None,
) -> tuple[str | None, str | None]:
    email_clean = (
        submit_email.strip()
        if isinstance(submit_email, str) and submit_email.strip()
        else None
    )
    url_clean = (
        submit_url.strip()
        if isinstance(submit_url, str) and submit_url.strip()
        else None
    )

    if email_clean is not None:
        if not re.match(EMAIL_REGEX, email_clean):
            raise ValueError(f"Invalid email syntax: {email_clean}")

    if email_clean is None and url_clean is None:
        raise ValueError(
            "Vacancy must have at least one contact method (submit_email or submit_url)."
        )

    return email_clean, url_clean


def create_vacancy(
    db: Session,
    vacancy_data: "VacancyCrewAI",
    source: DataSource = DataSource.linkedin,
) -> Vacancy:
    """Create a new vacancy from CrewAI data."""
    submit_email, submit_url = _normalize_and_validate_contacts(
        vacancy_data.submit_email, vacancy_data.submit_url
    )
    vacancy = Vacancy(
        title=vacancy_data.title,
        text=vacancy_data.text,
        submit_email=submit_email,
        submit_url=submit_url,
        visa_status=vacancy_data.visa_status,
        source=source,
    )
    db.add(vacancy)
    db.commit()
    db.refresh(vacancy)
    return vacancy


def create_vacancy_direct(
    db: Session,
    title: str,
    text: str,
    submit_email: str | None = None,
    submit_url: str | None = None,
    source: DataSource = DataSource.linkedin,
    visa_status: VisaStatus = VisaStatus.not_mentioned,
) -> Vacancy:
    """Create a new vacancy record from direct field attributes."""
    clean_email, clean_url = _normalize_and_validate_contacts(submit_email, submit_url)
    vacancy = Vacancy(
        title=title,
        text=text,
        submit_email=clean_email,
        submit_url=clean_url,
        source=source,
        visa_status=visa_status,
    )
    db.add(vacancy)
    db.commit()
    db.refresh(vacancy)
    return vacancy


def save_vacancy(
    title: str,
    text: str,
    submit_email: str | None = None,
    submit_url: str | None = None,
    source: DataSource = DataSource.linkedin,
    visa_status: VisaStatus = VisaStatus.not_mentioned,
    db: Session | None = None,
) -> Vacancy:
    """Save a vacancy record to SQLite database."""
    if db is not None:
        return create_vacancy_direct(
            db=db,
            title=title,
            text=text,
            submit_email=submit_email,
            submit_url=submit_url,
            source=source,
            visa_status=visa_status,
        )

    from ljpa_reworked.database import SessionLocal

    with SessionLocal() as session:
        return create_vacancy_direct(
            db=session,
            title=title,
            text=text,
            submit_email=submit_email,
            submit_url=submit_url,
            source=source,
            visa_status=visa_status,
        )


def get_vacancy_by_id(db: Session, vacancy_id: int) -> Vacancy | None:
    """Get vacancy by ID."""
    return (
        db.query(Vacancy)
        .filter(and_(Vacancy.id == vacancy_id, Vacancy.deleted.is_(False)))
        .first()
    )


def get_eligble_vacancies(
    db: Session,
    statuses: list[VacancyStatus] | None = None,
) -> list[Vacancy]:
    """Get eligible vacancies for review."""
    if statuses is None:
        statuses = [
            VacancyStatus.created,
            VacancyStatus.updated,
            VacancyStatus.review_error,
        ]
    return (
        db.query(Vacancy)
        .filter(
            and_(
                Vacancy.visa_status.in_(
                    [VisaStatus.provided, VisaStatus.not_mentioned]
                ),
                Vacancy.deleted.is_(False),
                Vacancy.status.in_(statuses),
            )
        )
        .all()
    )


def transition_vacancy_status(
    db: Session,
    vacancy_id: int,
    target_status: VacancyStatus,
    allowed_from_statuses: list[VacancyStatus] | None = None,
    commit: bool = True,
) -> Vacancy:
    """Transition a vacancy's status with validation and terminal status protection."""
    vacancy = get_vacancy_by_id(db, vacancy_id)
    if not vacancy:
        raise ValueError(f"Vacancy with id {vacancy_id} not found.")

    if vacancy.status == target_status:
        return vacancy

    if vacancy.status in TERMINAL_STATUSES:
        if allowed_from_statuses is None or vacancy.status not in allowed_from_statuses:
            raise ValueError(
                f"Cannot transition vacancy {vacancy_id} from terminal status '{vacancy.status.value}' to '{target_status.value}'."
            )

    if (
        allowed_from_statuses is not None
        and vacancy.status not in allowed_from_statuses
    ):
        allowed_str = [
            s.value if hasattr(s, "value") else str(s) for s in allowed_from_statuses
        ]
        raise ValueError(
            f"Cannot transition vacancy {vacancy_id} from status '{vacancy.status.value}' to '{target_status.value}'. Transition is not allowed (allowed source statuses: {allowed_str})."
        )

    vacancy.status = target_status
    if commit:
        db.commit()
        db.refresh(vacancy)
    return vacancy


def confirm_email_application_submitted(
    db: Session,
    vacancy_id: int,
    applied_at: datetime | None = None,
) -> Vacancy:
    """Transition vacancy to applied status and stamp applied_at timestamp only after confirmed email send."""
    vacancy = transition_vacancy_status(
        db=db,
        vacancy_id=vacancy_id,
        target_status=VacancyStatus.applied,
        commit=False,
    )
    vacancy.applied_at = applied_at or datetime.utcnow()
    db.commit()
    db.refresh(vacancy)
    return vacancy


def get_all_vacancies(db: Session, skip: int = 0, limit: int = 100) -> list[Vacancy]:
    """Get all non-deleted vacancies."""
    return (
        db.query(Vacancy)
        .filter(Vacancy.deleted.is_(False))
        .offset(skip)
        .limit(limit)
        .all()
    )


def search_vacancies(db: Session, keyword: str) -> list[Vacancy]:
    """Search vacancies by title or text."""
    return (
        db.query(Vacancy)
        .filter(
            and_(
                or_(Vacancy.title.contains(keyword), Vacancy.text.contains(keyword)),
                Vacancy.deleted.is_(False),
            )
        )
        .all()
    )


def get_vacancies_by_source(db: Session, source: str) -> list[Vacancy]:
    """Get vacancies from specific source."""
    return (
        db.query(Vacancy)
        .filter(and_(Vacancy.source == source, Vacancy.deleted.is_(False)))
        .all()
    )


def get_vacancies_by_visa_status(db: Session, visa_status: str) -> list[Vacancy]:
    """Get vacancies by visa status."""
    return (
        db.query(Vacancy)
        .filter(and_(Vacancy.visa_status == visa_status, Vacancy.deleted.is_(False)))
        .all()
    )


def soft_delete_vacancy(db: Session, vacancy_id: int) -> bool:
    """Soft delete vacancy."""
    vacancy = db.query(Vacancy).filter(Vacancy.id == vacancy_id).first()
    if vacancy:
        vacancy.deleted = True
        db.commit()
        return True
    return False


def update_vacancy(db: Session, vacancy_id: int, **kwargs) -> Vacancy | None:
    """Update vacancy fields."""
    vacancy = get_vacancy_by_id(db, vacancy_id)
    if vacancy:
        if "status" in kwargs:
            target_status = kwargs.pop("status")
            transition_vacancy_status(db, vacancy_id, target_status)
        for key, value in kwargs.items():
            if hasattr(vacancy, key):
                setattr(vacancy, key, value)
        db.commit()
        db.refresh(vacancy)
    return vacancy


def upsert_vacancy_by_url(
    db: Session,
    vacancy_data: dict,
) -> tuple[Vacancy | None, bool]:
    """Upsert a vacancy by URL or submit_email.

    If submit_url is present:
    - If submit_url exists in DB: refreshes source-owned fields and sets status=VacancyStatus.updated.
    - If submit_url is new: creates a new Vacancy with status=VacancyStatus.created.
    If submit_url is absent but submit_email is present:
    - Inserts a new Vacancy (email-only) with status=VacancyStatus.created without URL deduplication.
    If both submit_url and submit_email are absent/blank:
    - Logs warning and returns (None, False).
    """
    raw_url = vacancy_data.get("submit_url")
    raw_email = vacancy_data.get("submit_email")

    url = str(raw_url).strip() if raw_url and str(raw_url).strip() else None
    email = str(raw_email).strip() if raw_email and str(raw_email).strip() else None

    if email is not None:
        if not re.match(EMAIL_REGEX, email):
            logger.warning("Skipping vacancy upsert: invalid email syntax '%s'", email)
            return None, False

    if not url and not email:
        logger.warning(
            "Skipping vacancy upsert: missing both submit_url and submit_email."
        )
        return None, False

    source = vacancy_data.get("source", DataSource.linkedin)
    visa_status = vacancy_data.get("visa_status", VisaStatus.not_mentioned)

    if url is not None:
        existing = db.query(Vacancy).filter(Vacancy.submit_url == url).first()
        if existing is None:
            vacancy = Vacancy(
                title=str(vacancy_data.get("title") or "Unknown Title"),
                text=str(vacancy_data.get("text") or ""),
                submit_email=email,
                submit_url=url,
                source=source,
                visa_status=visa_status,
                status=VacancyStatus.created,
            )
            try:
                db.add(vacancy)
                db.commit()
                db.refresh(vacancy)
                return vacancy, True
            except IntegrityError:
                db.rollback()
                existing = db.query(Vacancy).filter(Vacancy.submit_url == url).first()
                if existing is None:
                    raise

        # Refresh source-owned fields on existing record
        if "title" in vacancy_data and vacancy_data["title"] is not None:
            existing.title = str(vacancy_data["title"])
        if "text" in vacancy_data and vacancy_data["text"] is not None:
            existing.text = str(vacancy_data["text"])
        if email is not None or "submit_email" in vacancy_data:
            existing.submit_email = email

        if "source" in vacancy_data and vacancy_data["source"] is not None:
            existing.source = vacancy_data["source"]
        if "visa_status" in vacancy_data and vacancy_data["visa_status"] is not None:
            existing.visa_status = vacancy_data["visa_status"]

        existing.status = VacancyStatus.updated

        db.commit()
        db.refresh(existing)
        return existing, False
    else:
        # Email-only vacancy insertion without URL deduplication
        vacancy = Vacancy(
            title=str(vacancy_data.get("title") or "Unknown Title"),
            text=str(vacancy_data.get("text") or ""),
            submit_email=email,
            submit_url=None,
            source=source,
            visa_status=visa_status,
            status=VacancyStatus.created,
        )
        db.add(vacancy)
        db.commit()
        db.refresh(vacancy)
        return vacancy, True
