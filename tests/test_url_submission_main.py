from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from ljpa_reworked.database import Base, init_db
from ljpa_reworked.main import process_eligible_vacancies
from ljpa_reworked.models.enums import VacancyStatus
from ljpa_reworked.operations.vacancy_ops import (
    confirm_application_submitted,
    create_vacancy_direct,
    get_eligible_url_vacancies,
)


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(bind_engine=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_get_eligible_url_vacancies_ordering_age_and_limit(db_session: Session):
    now = datetime.utcnow()
    # Create 25 URL vacancies with varying created_at
    created_vacancies = []
    for i in range(25):
        v = create_vacancy_direct(
            db=db_session,
            title=f"URL Job {i}",
            text="Text",
            submit_url=f"https://example.com/job/{i}",
        )
        # Shift created_at by i days ago
        v.created_at = now - timedelta(days=i)
        db_session.commit()
        created_vacancies.append(v)

    # Old vacancy (> 60 days)
    v_old = create_vacancy_direct(
        db=db_session,
        title="Old Job",
        text="Text",
        submit_url="https://example.com/old",
    )
    v_old.created_at = now - timedelta(days=61)
    db_session.commit()

    # Applied vacancy
    v_applied = create_vacancy_direct(
        db=db_session,
        title="Applied Job",
        text="Text",
        submit_url="https://example.com/applied",
    )
    confirm_application_submitted(db=db_session, vacancy_id=v_applied.id)

    # Query 20 freshest eligible vacancies
    results = get_eligible_url_vacancies(db=db_session, limit=20, max_age_days=60)

    assert len(results) == 20
    # Old vacancy and applied vacancy must not be in results
    result_ids = [r.id for r in results]
    assert v_old.id not in result_ids
    assert v_applied.id not in result_ids

    # Newest first ordering: i=0 is freshest
    assert results[0].id == created_vacancies[0].id
    assert results[-1].id == created_vacancies[19].id


def test_process_eligible_vacancies_url_submission_success(db_session: Session):
    v = create_vacancy_direct(
        db=db_session,
        title="URL Only Job",
        text="Description",
        submit_url="https://example.com/careers/submit",
    )

    eval_obj = MagicMock(rating=80)
    mock_resume_obj = MagicMock()
    mock_orm_resume = MagicMock(path="resume_123.pdf")

    with (
        patch("ljpa_reworked.main.crewai_evaluate_vacancy", return_value=eval_obj),
        patch("ljpa_reworked.main.create_evaluation"),
        patch(
            "ljpa_reworked.main.crewai_generate_resume_with_retry",
            return_value=(mock_resume_obj, "/tmp/fake.pdf"),
        ),
        patch("ljpa_reworked.main.save_resume", return_value=mock_orm_resume),
        patch("ljpa_reworked.main.harness_submit", return_value=0) as mock_submit,
    ):
        process_eligible_vacancies(db=db_session, vacancies=[v])

        db_session.refresh(v)
        assert v.status == VacancyStatus.applied
        assert v.applied_at is not None
        mock_submit.assert_called_once()
        call_kwargs = mock_submit.call_args.kwargs
        assert call_kwargs["vacancy_url"] == "https://example.com/careers/submit"
        assert call_kwargs["resume_path"].endswith("resume_123.pdf")


def test_process_eligible_vacancies_url_submission_failure(db_session: Session):
    v = create_vacancy_direct(
        db=db_session,
        title="Failing URL Job",
        text="Description",
        submit_url="https://example.com/careers/fail",
    )

    eval_obj = MagicMock(rating=80)
    mock_resume_obj = MagicMock()
    mock_orm_resume = MagicMock(path="resume_fail.pdf")

    with (
        patch("ljpa_reworked.main.crewai_evaluate_vacancy", return_value=eval_obj),
        patch("ljpa_reworked.main.create_evaluation"),
        patch(
            "ljpa_reworked.main.crewai_generate_resume_with_retry",
            return_value=(mock_resume_obj, "/tmp/fake.pdf"),
        ),
        patch("ljpa_reworked.main.save_resume", return_value=mock_orm_resume),
        patch("ljpa_reworked.main.harness_submit", return_value=1) as mock_submit,
    ):
        process_eligible_vacancies(db=db_session, vacancies=[v])

        db_session.refresh(v)
        assert v.status == VacancyStatus.application_error
        assert v.applied_at is None
        mock_submit.assert_called_once()


def test_process_eligible_vacancies_no_duplicate_url_submission_if_already_applied_via_email(
    db_session: Session,
):
    v = create_vacancy_direct(
        db=db_session,
        title="Email and URL Job",
        text="Description",
        submit_email="hr@company.com",
        submit_url="https://example.com/careers/apply",
    )

    eval_obj = MagicMock(rating=80)
    mock_resume_obj = MagicMock()
    mock_orm_resume = MagicMock(path="resume_both.pdf")
    mock_email_obj = MagicMock()
    mock_orm_email = MagicMock()

    with (
        patch("ljpa_reworked.main.crewai_evaluate_vacancy", return_value=eval_obj),
        patch("ljpa_reworked.main.create_evaluation"),
        patch(
            "ljpa_reworked.main.crewai_generate_resume_with_retry",
            return_value=(mock_resume_obj, "/tmp/fake.pdf"),
        ),
        patch("ljpa_reworked.main.save_resume", return_value=mock_orm_resume),
        patch("ljpa_reworked.main.verified_recipient", return_value=True),
        patch("ljpa_reworked.main.crewai_generate_email", return_value=mock_email_obj),
        patch("ljpa_reworked.main.create_email", return_value=mock_orm_email),
        patch("ljpa_reworked.main.send_email"),
        patch("ljpa_reworked.main.harness_submit") as mock_harness_submit,
    ):
        process_eligible_vacancies(db=db_session, vacancies=[v])

        db_session.refresh(v)
        assert v.status == VacancyStatus.applied
        # Should not be called because email route succeeded and marked it applied
        mock_harness_submit.assert_not_called()
