from typing import TYPE_CHECKING

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from ljpa_reworked.models.crewai_pydantic_models import VacancyCrewAI
from ljpa_reworked.models.crewai_pydantic_models import VisaStatus
from ljpa_reworked.models.database_models import DataSource, Vacancy


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


def get_eligble_vacancies(db: Session) -> list[Vacancy]:
    """Get eligible vacancies."""
    return db.query(Vacancy).filter(
        and_(
            Vacancy.visa_status.in_([VisaStatus.provided, VisaStatus.not_mentioned]),
            Vacancy.deleted.is_(False),
            Vacancy.processed.is_(False),
        )
    )


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
        for key, value in kwargs.items():
            if hasattr(vacancy, key):
                setattr(vacancy, key, value)
        db.commit()
        db.refresh(vacancy)
    return vacancy
