from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from ljpa_reworked.database import Base, init_db
from ljpa_reworked.models.crewai_pydantic_models import BasicEvaluationCrewAI
from ljpa_reworked.models.enums import VacancyStatus
from ljpa_reworked.operations.evaluation_ops import (
    adjusted_score,
    build_ranked_submission_queue,
    create_evaluation,
)
from ljpa_reworked.operations.vacancy_ops import create_vacancy_direct


def _session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(bind_engine=engine)
    return sessionmaker(bind=engine)(), engine


def _vacancy(db, title):
    return create_vacancy_direct(
        db,
        title=title,
        text=f"{title} text",
        submit_url=f"https://example.com/{title.lower().replace(' ', '-')}",
    )


def test_adjusted_score_with_visa_probability():
    now = datetime(2026, 8, 15, 12, 0, 0)
    created_now = now
    created_two_days_ago = now - timedelta(days=2)

    # 1. 100% visa probability, fresh vacancy (0 days) -> score = rating
    assert adjusted_score(90, created_now, visa_probability=100, now=now) == 90.0

    # 2. 56% visa probability, fresh vacancy:
    # visa penalty = (100 - 56) / 2.2 = 44 / 2.2 = 20.0
    # score = 90 - 0 - 20.0 = 70.0
    assert (
        pytest.approx(adjusted_score(90, created_now, visa_probability=56, now=now))
        == 70.0
    )

    # 3. 56% visa probability, 2 days old vacancy (age_tax = 2 * 1.5 = 3.0):
    # score = 90 - 3.0 - 20.0 = 67.0
    assert (
        pytest.approx(
            adjusted_score(90, created_two_days_ago, visa_probability=56, now=now)
        )
        == 67.0
    )

    # 4. 0% visa probability: penalty = 100 / 2.2 = 45.4545...
    # rating 90 -> score = 90 - 45.4545... = 44.5454... (which is < 50)
    assert pytest.approx(
        adjusted_score(90, created_now, visa_probability=0, now=now)
    ) == 90.0 - (100.0 / 2.2)


def test_build_ranked_submission_queue_sorts_and_deletes_below_fifty():
    db, engine = _session()
    try:
        now = datetime(2026, 8, 15, 12, 0, 0)
        v_high_visa = _vacancy(db, "High Visa")
        v_low_visa = _vacancy(db, "Low Visa")
        v_failing_visa = _vacancy(db, "Failing Visa")

        for v in (v_high_visa, v_low_visa, v_failing_visa):
            v.created_at = now
            v.status = VacancyStatus.application_prepared
            from ljpa_reworked.models.database_models import Resume

            db.add(
                Resume(
                    vacancy_id=v.id,
                    fullname="Test",
                    email="test@example.com",
                    summary="Test",
                )
            )

        # High visa: rating 80, visa 100 -> score = 80
        create_evaluation(
            db,
            v_high_visa.id,
            BasicEvaluationCrewAI(
                summary="Good match",
                rating=80,
                visa_probability=100,
            ),
        )

        # Low visa: rating 90, visa 56 -> score = 90 - 20 = 70
        create_evaluation(
            db,
            v_low_visa.id,
            BasicEvaluationCrewAI(
                summary="High rating but lower visa",
                rating=90,
                visa_probability=56,
            ),
        )

        # Failing visa: rating 70, visa 12 -> penalty = 88 / 2.2 = 40 -> score = 30 (< 50)
        create_evaluation(
            db,
            v_failing_visa.id,
            BasicEvaluationCrewAI(
                summary="Visa sponsorship unlikely",
                rating=70,
                visa_probability=12,
            ),
        )

        ranked = build_ranked_submission_queue(db, now=now)

        # Should be sorted: High Visa (score 80) then Low Visa (score 70)
        assert len(ranked) == 2
        assert ranked[0].vacancy.id == v_high_visa.id
        assert pytest.approx(ranked[0].score) == 80.0
        assert ranked[1].vacancy.id == v_low_visa.id
        assert pytest.approx(ranked[1].score) == 70.0

        # Failing visa (< 50) must be marked as deleted
        assert db.get(type(v_failing_visa), v_failing_visa.id).deleted is True
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_basic_evaluation_crewai_visa_probability_validation():
    # Valid
    ev = BasicEvaluationCrewAI(
        summary="Test",
        rating=85,
        visa_probability=75,
    )
    assert ev.visa_probability == 75

    # Default is 100
    ev_default = BasicEvaluationCrewAI(summary="Test", rating=85)
    assert ev_default.visa_probability == 100

    # Bounds check
    with pytest.raises(ValidationError):
        BasicEvaluationCrewAI(summary="Test", rating=85, visa_probability=150)

    with pytest.raises(ValidationError):
        BasicEvaluationCrewAI(summary="Test", rating=85, visa_probability=-10)
