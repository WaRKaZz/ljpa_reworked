from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session

from ljpa_reworked.config import MINIMUM_SCORE
from ljpa_reworked.models.crewai_pydantic_models import BasicEvaluationCrewAI
from ljpa_reworked.models.database_models import BasicEvaluation, Resume, Vacancy
from ljpa_reworked.models.enums import VacancyStatus

DAILY_SCORE_PENALTY = 1.5


@dataclass(frozen=True)
class RankedVacancy:
    vacancy: Vacancy
    score: float


def adjusted_score(
    rating: int,
    created_at: datetime,
    visa_probability: int = 100,
    *,
    now: datetime,
) -> float:
    """Return score after age penalty and visa sponsorship penalty.

    Formula: rating - (age_days * 1.5) - ((100 - visa_probability) / 2.2)
    """
    age_days = max(0, (now - created_at).days)
    age_tax = age_days * DAILY_SCORE_PENALTY
    visa_penalty = (100.0 - visa_probability) / 2.2
    return rating - age_tax - visa_penalty


def build_ranked_submission_queue(
    db: Session, *, now: datetime | None = None
) -> list[RankedVacancy]:
    """Discard low-score vacancies and rank unapplied-via-URL error-free vacancies with existing resumes."""
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
        .join(Resume, Resume.vacancy_id == Vacancy.id)
        .filter(
            Vacancy.deleted.is_(False),
            Vacancy.status.notin_(
                [
                    VacancyStatus.submitted_via_url,
                    VacancyStatus.submitted_via_all,
                    VacancyStatus.application_error,
                    VacancyStatus.review_error,
                    VacancyStatus.rejected,
                    VacancyStatus.withdrawn,
                    VacancyStatus.expired,
                    VacancyStatus.archived,
                ]
            ),
            Vacancy.submit_url.isnot(None),
            Vacancy.submit_url != "",
        )
        .all()
    )
    ranked: list[RankedVacancy] = []
    for vacancy, evaluation in rows:
        visa_prob = getattr(evaluation, "visa_probability", 100)
        if visa_prob is None:
            visa_prob = 100
        score = adjusted_score(
            evaluation.rating, vacancy.created_at, visa_probability=visa_prob, now=now
        )
        if score < MINIMUM_SCORE:
            vacancy.deleted = True
            continue
        ranked.append(RankedVacancy(vacancy=vacancy, score=score))
    db.commit()
    return sorted(ranked, key=lambda item: (-item.score, item.vacancy.id))


def build_ranked_email_submission_queue(
    db: Session, *, now: datetime | None = None
) -> list[RankedVacancy]:
    """Discard low-score vacancies and rank unapplied-via-email error-free vacancies with existing resumes."""
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
        .join(Resume, Resume.vacancy_id == Vacancy.id)
        .filter(
            Vacancy.deleted.is_(False),
            Vacancy.status.notin_(
                [
                    VacancyStatus.submitted_via_email,
                    VacancyStatus.submitted_via_all,
                    VacancyStatus.application_error,
                    VacancyStatus.review_error,
                    VacancyStatus.rejected,
                    VacancyStatus.withdrawn,
                    VacancyStatus.expired,
                    VacancyStatus.archived,
                ]
            ),
            Vacancy.submit_email.isnot(None),
            Vacancy.submit_email != "",
        )
        .all()
    )
    ranked: list[RankedVacancy] = []
    for vacancy, evaluation in rows:
        visa_prob = getattr(evaluation, "visa_probability", 100)
        if visa_prob is None:
            visa_prob = 100
        score = adjusted_score(
            evaluation.rating, vacancy.created_at, visa_probability=visa_prob, now=now
        )
        if score < MINIMUM_SCORE:
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
        visa_probability=evaluation_data.visa_probability,
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
    visa_probability: int | None = None,
) -> BasicEvaluation | None:
    evaluation = get_evaluation_by_id(db, evaluation_id)
    if evaluation:
        if summary is not None:
            evaluation.summary = summary
        if rating is not None:
            evaluation.rating = rating
        if visa_probability is not None:
            evaluation.visa_probability = visa_probability
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
