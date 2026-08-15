from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session

from ljpa_reworked.models.crewai_pydantic_models import BasicEvaluationCrewAI
from ljpa_reworked.models.database_models import BasicEvaluation, Vacancy
from ljpa_reworked.models.enums import VacancyStatus

MINIMUM_SCORE = 50.0
DAILY_SCORE_PENALTY = 1.5


@dataclass(frozen=True)
class RankedVacancy:
    vacancy: Vacancy
    score: float


def adjusted_score(rating: int, created_at: datetime, *, now: datetime) -> float:
    """Return score after a 1.5-point penalty for every full day of age."""
    age_days = max(0, (now - created_at).days)
    return rating - (age_days * DAILY_SCORE_PENALTY)


def build_ranked_submission_queue(
    db: Session, *, now: datetime | None = None
) -> list[RankedVacancy]:
    """Discard low-score vacancies and rank prepared URL applications."""
    now = now or datetime.now(UTC).replace(tzinfo=None)
    latest_evaluation_id = (
        db.query(BasicEvaluation.vacancy_id, func.max(BasicEvaluation.id).label("id"))
        .group_by(BasicEvaluation.vacancy_id)
        .subquery()
    )
    rows = (
        db.query(Vacancy, BasicEvaluation)
        .join(latest_evaluation_id, latest_evaluation_id.c.vacancy_id == Vacancy.id)
        .join(BasicEvaluation, BasicEvaluation.id == latest_evaluation_id.c.id)
        .filter(
            Vacancy.deleted.is_(False),
            Vacancy.status == VacancyStatus.application_prepared,
            Vacancy.submit_url.isnot(None),
            Vacancy.submit_url != "",
        )
        .all()
    )
    ranked: list[RankedVacancy] = []
    for vacancy, evaluation in rows:
        score = adjusted_score(evaluation.rating, vacancy.created_at, now=now)
        if evaluation.rating < MINIMUM_SCORE or score < MINIMUM_SCORE:
            vacancy.deleted = True
            continue
        ranked.append(RankedVacancy(vacancy=vacancy, score=score))
    db.commit()
    return sorted(ranked, key=lambda item: (-item.score, item.vacancy.id))


def create_evaluation(
    db: Session, vacancy_id: int, evaluation_data: BasicEvaluationCrewAI
) -> BasicEvaluation:
    evaluation = BasicEvaluation(
        vacancy_id=vacancy_id,
        summary=evaluation_data.summary,
        rating=evaluation_data.rating,
    )
    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)
    return evaluation


def get_evaluation_by_id(db: Session, evaluation_id: int) -> BasicEvaluation | None:
    return db.query(BasicEvaluation).filter(BasicEvaluation.id == evaluation_id).first()


def get_evaluation_by_vacancy(db: Session, vacancy_id: int) -> BasicEvaluation | None:
    return (
        db.query(BasicEvaluation)
        .filter(BasicEvaluation.vacancy_id == vacancy_id)
        .first()
    )


def update_evaluation(
    db: Session,
    evaluation_id: int,
    summary: str | None = None,
    rating: int | None = None,
) -> BasicEvaluation | None:
    evaluation = get_evaluation_by_id(db, evaluation_id)
    if evaluation:
        if summary is not None:
            evaluation.summary = summary
        if rating is not None:
            evaluation.rating = rating
        db.commit()
        db.refresh(evaluation)
    return evaluation


def get_evaluations_by_rating_range(
    db: Session, min_rating: int, max_rating: int
) -> list[BasicEvaluation]:
    return (
        db.query(BasicEvaluation)
        .filter(BasicEvaluation.rating.between(min_rating, max_rating))
        .all()
    )


def get_top_rated_vacancies(db: Session, limit: int = 10) -> list[Vacancy]:
    return (
        db.query(Vacancy)
        .join(BasicEvaluation)
        .filter(Vacancy.deleted.is_(False))  # <-- FIXED
        .order_by(desc(BasicEvaluation.rating))
        .limit(limit)
        .all()
    )


def get_unrated_vacancies(db: Session) -> list[Vacancy]:
    return (
        db.query(Vacancy)
        .outerjoin(BasicEvaluation)
        .filter(
            and_(BasicEvaluation.id.is_(None), Vacancy.deleted.is_(False))
        )  # <-- FIXED
        .all()
    )


def delete_evaluation(db: Session, evaluation_id: int) -> bool:
    evaluation = get_evaluation_by_id(db, evaluation_id)
    if evaluation:
        db.delete(evaluation)
        db.commit()
        return True
    return False
