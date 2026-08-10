from typing import TYPE_CHECKING

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from ljpa_reworked.models.crewai_pydantic_models import VacancyCrewAI
from ljpa_reworked.models.crewai_pydantic_models import VisaStatus
from ljpa_reworked.models.database_models import DataSource, Vacancy
from ljpa_reworked.models.enums import VacancyStatus

TERMINAL_STATUSES = {
    VacancyStatus.applied,
    VacancyStatus.withdrawn,
    VacancyStatus.expired,
    VacancyStatus.archived,
}


def create_vacancy(
    db: Session,
    vacancy_data: "VacancyCrewAI",
    source: DataSource = DataSource.linkedin,
) -> Vacancy:
    """Create a new vacancy from CrewAI data."""
    vacancy = Vacancy(
        title=vacancy_data.title,
        text=vacancy_data.text,
        credentials=vacancy_data.credentials,
        visa_status=vacancy_data.visa_status,
        url=vacancy_data.url,
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
    credentials: str | None = None,
    url: str | None = None,
    source: DataSource = DataSource.linkedin,
    visa_status: VisaStatus = VisaStatus.not_mentioned,
) -> Vacancy:
    """Create a new vacancy record from direct field attributes."""
    vacancy = Vacancy(
        title=title,
        text=text,
        credentials=credentials,
        url=url,
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
    credentials: str | None = None,
    url: str | None = None,
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
            credentials=credentials,
            url=url,
            source=source,
            visa_status=visa_status,
        )

    from ljpa_reworked.database import SessionLocal

    with SessionLocal() as session:
        return create_vacancy_direct(
            db=session,
            title=title,
            text=text,
            credentials=credentials,
            url=url,
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
        statuses = [VacancyStatus.created, VacancyStatus.review_error]
    return (
        db.query(Vacancy)
        .filter(
            and_(
                Vacancy.visa_status.in_([VisaStatus.provided, VisaStatus.not_mentioned]),
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

    if allowed_from_statuses is not None and vacancy.status not in allowed_from_statuses:
        allowed_str = [s.value if hasattr(s, "value") else str(s) for s in allowed_from_statuses]
        raise ValueError(
            f"Cannot transition vacancy {vacancy_id} from status '{vacancy.status.value}' to '{target_status.value}'. Transition is not allowed (allowed source statuses: {allowed_str})."
        )

    vacancy.status = target_status
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

