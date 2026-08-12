from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from ljpa_reworked.database import Base, init_db
from ljpa_reworked.main import process_eligible_vacancies
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
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_process_eligible_vacancies_rating_threshold(db_session: Session):
    """Rating <= 50 rejects vacancy without creating resume. Rating > 50 creates resume."""
    v1 = create_vacancy_direct(
        db=db_session,
        title="Low Rating Job",
        text="Description 1",
        submit_email="hr1@example.com",
    )
    v2 = create_vacancy_direct(
        db=db_session,
        title="High Rating Job",
        text="Description 2",
        submit_email="hr2@example.com",
    )

    eval_v1 = MagicMock(rating=50)
    eval_v2 = MagicMock(rating=51)

    eval_side_effects = [eval_v1, eval_v2]

    def mock_eval(vacancy):
        return eval_side_effects.pop(0)

    mock_resume_obj = MagicMock()
    mock_orm_resume = MagicMock(path="resumes/fake.pdf")

    with (
        patch(
            "ljpa_reworked.main.crewai_evaluate_vacancy", side_effect=mock_eval
        ) as mock_crew_eval,
        patch("ljpa_reworked.main.create_evaluation") as mock_create_eval,
        patch(
            "ljpa_reworked.main.crewai_generate_resume_with_retry",
            return_value=(mock_resume_obj, "/tmp/fake.pdf"),
        ) as mock_gen_resume,
        patch(
            "ljpa_reworked.main.save_resume", return_value=mock_orm_resume
        ) as mock_save_resume,
        patch(
            "ljpa_reworked.main.verified_recipient", return_value=False
        ),
    ):
        process_eligible_vacancies(db=db_session, vacancies=[v1, v2])

        assert mock_crew_eval.call_count == 2
        assert mock_create_eval.call_count == 2

        # v1 (rating 50) must be rejected
        db_session.refresh(v1)
        assert v1.status == VacancyStatus.rejected

        # v2 (rating 51) must generate resume
        mock_gen_resume.assert_called_once_with(vacancy=v2, evaluation=eval_v2)
        mock_save_resume.assert_called_once_with(
            mock_resume_obj, v2, db_session, temp_pdf_path="/tmp/fake.pdf"
        )


def test_process_eligible_vacancies_verified_email_path(db_session: Session):
    """Verified email recipient triggers crewai_generate_email, create_email, send_email, and confirm."""
    import ljpa_reworked.main as main_module

    assert not hasattr(main_module, "send_telegram_post")

    v = create_vacancy_direct(
        db=db_session,
        title="Email Dev Job",
        text="Description",
        submit_email="hr@company.com",
    )

    eval_obj = MagicMock(rating=80)
    mock_resume_obj = MagicMock()
    mock_orm_resume = MagicMock(path="resumes/resume.pdf")
    mock_email_obj = MagicMock()
    mock_orm_email = MagicMock()

    with (
        patch(
            "ljpa_reworked.main.crewai_evaluate_vacancy", return_value=eval_obj
        ),
        patch("ljpa_reworked.main.create_evaluation"),
        patch(
            "ljpa_reworked.main.crewai_generate_resume_with_retry",
            return_value=(mock_resume_obj, "/tmp/fake.pdf"),
        ),
        patch("ljpa_reworked.main.save_resume", return_value=mock_orm_resume),
        patch(
            "ljpa_reworked.main.verified_recipient", return_value=True
        ) as mock_verified,
        patch(
            "ljpa_reworked.main.crewai_generate_email", return_value=mock_email_obj
        ) as mock_gen_email,
        patch(
            "ljpa_reworked.main.create_email", return_value=mock_orm_email
        ) as mock_create_email,
        patch("ljpa_reworked.main.send_email") as mock_send_email,
        patch(
            "ljpa_reworked.main.confirm_email_application_submitted"
        ) as mock_confirm,
        patch("ljpa_reworked.main.harness_submit", return_value=None),
    ):
        process_eligible_vacancies(db=db_session, vacancies=[v])

        mock_verified.assert_called_once_with("hr@company.com", db_session)
        mock_gen_email.assert_called_once_with(vacancy=v)
        mock_create_email.assert_called_once_with(
            db=db_session,
            vacancy_id=v.id,
            email_data=mock_email_obj,
            recipient="hr@company.com",
            resume_path="resumes/resume.pdf",
        )
        mock_send_email.assert_called_once_with(mock_orm_email)
        mock_confirm.assert_called_once_with(db=db_session, vacancy_id=v.id)


@pytest.mark.parametrize(
    "submit_email,submit_url,is_verified",
    [
        (None, "https://example.com/careers/apply-form", False),
        (None, "https://example.com/apply-no-email", False),
        ("unverified@company.com", None, False),
        (None, "mailto:hr@company.com", False),
    ],
)
def test_process_eligible_vacancies_unverified_or_missing_email(
    db_session: Session, submit_email, submit_url, is_verified
):
    """When email is missing or unverified, status transitions to application_prepared without email or telegram execution."""
    import ljpa_reworked.main as main_module

    assert not hasattr(main_module, "send_telegram_post")

    v = create_vacancy_direct(
        db=db_session,
        title="Unverified Email Job",
        text="Description",
        submit_email=submit_email,
        submit_url=submit_url,
    )

    eval_obj = MagicMock(rating=75)
    mock_resume_obj = MagicMock()
    mock_orm_resume = MagicMock(path="resumes/resume.pdf")

    with (
        patch(
            "ljpa_reworked.main.crewai_evaluate_vacancy", return_value=eval_obj
        ),
        patch("ljpa_reworked.main.create_evaluation"),
        patch(
            "ljpa_reworked.main.crewai_generate_resume_with_retry",
            return_value=(mock_resume_obj, "/tmp/fake.pdf"),
        ),
        patch("ljpa_reworked.main.save_resume", return_value=mock_orm_resume),
        patch(
            "ljpa_reworked.main.verified_recipient", return_value=is_verified
        ),
        patch("ljpa_reworked.main.crewai_generate_email") as mock_gen_email,
        patch("ljpa_reworked.main.create_email") as mock_create_email,
        patch("ljpa_reworked.main.send_email") as mock_send_email,
        patch(
            "ljpa_reworked.main.confirm_email_application_submitted"
        ) as mock_confirm,
        patch("ljpa_reworked.main.harness_submit", return_value=None),
    ):
        process_eligible_vacancies(db=db_session, vacancies=[v])

        db_session.refresh(v)
        assert v.status == VacancyStatus.application_prepared

        mock_gen_email.assert_not_called()
        mock_create_email.assert_not_called()
        mock_send_email.assert_not_called()
        mock_confirm.assert_not_called()
