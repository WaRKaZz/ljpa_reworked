from sqlalchemy import and_, desc
from sqlalchemy.orm import Session

from ljpa_reworked.models.crewai_pydantic_models import BasicEvaluationCrewAI
from ljpa_reworked.models.database_models import BasicEvaluation, Vacancy


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
