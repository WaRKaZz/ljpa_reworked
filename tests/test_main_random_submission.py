from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from ljpa_reworked.database import Base, init_db
from ljpa_reworked.main import SUBMIT_PROMPT_FILE, submit_one_random_vacancy
from ljpa_reworked.models.enums import VacancyStatus
from ljpa_reworked.operations.vacancy_ops import create_vacancy_direct


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(bind_engine=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_submit_one_random_vacancy_renders_then_submits(db_session):
    vacancy = create_vacancy_direct(
        db=db_session,
        title="URL Job",
        text="Description",
        submit_url="https://example.com/apply",
    )
    evaluation = MagicMock(rating=80)
    rendered = MagicMock(path="resume_7.pdf")

    with (
        patch("ljpa_reworked.main.random.choice", return_value=vacancy),
        patch("ljpa_reworked.main.crewai_evaluate_vacancy", return_value=evaluation),
        patch("ljpa_reworked.main.create_evaluation"),
        patch("ljpa_reworked.main.crewai_generate_resume_with_retry", return_value=(MagicMock(), "/tmp/resume.pdf")),
        patch("ljpa_reworked.main.save_resume", return_value=rendered) as save,
        patch("ljpa_reworked.main.harness_submit", return_value=0) as submit,
    ):
        assert submit_one_random_vacancy(db_session) == 0

    save.assert_called_once()
    assert submit.call_args.kwargs["vacancy_url"] == "https://example.com/apply"
    assert submit.call_args.kwargs["resume_path"] == "/app/resources/resumes/resume_7.pdf"
    assert submit.call_args.kwargs["prompt_file"] == SUBMIT_PROMPT_FILE
    assert submit.call_args.kwargs["timeout"] == "4h"
    db_session.refresh(vacancy)
    assert vacancy.status == VacancyStatus.submitted_via_url
    assert vacancy.applied_at is not None


def test_submit_one_random_vacancy_marks_harness_failure(db_session):
    vacancy = create_vacancy_direct(
        db=db_session,
        title="URL Job",
        text="Description",
        submit_url="https://example.com/apply",
    )
    with (
        patch("ljpa_reworked.main.random.choice", return_value=vacancy),
        patch("ljpa_reworked.main.crewai_evaluate_vacancy", return_value=MagicMock(rating=80)),
        patch("ljpa_reworked.main.create_evaluation"),
        patch("ljpa_reworked.main.crewai_generate_resume_with_retry", return_value=(MagicMock(), "/tmp/resume.pdf")),
        patch("ljpa_reworked.main.save_resume", return_value=MagicMock(path="resume_7.pdf")),
        patch("ljpa_reworked.main.harness_submit", return_value=1),
    ):
        assert submit_one_random_vacancy(db_session) == 1

    db_session.refresh(vacancy)
    assert vacancy.status == VacancyStatus.application_error
