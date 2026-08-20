from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ljpa_reworked.database import init_db
from ljpa_reworked.models.crewai_pydantic_models import VisaStatus
from ljpa_reworked.models.database_models import DataSource, Vacancy
from ljpa_reworked.models.enums import VacancyStatus
from ljpa_reworked.operations.vacancy_ops import (
    confirm_email_application_submitted,
    confirm_url_application_submitted,
)


def _vacancy(session):
    vacancy = Vacancy(
        title="Test vacancy",
        text="Test description",
        submit_email="apply@example.com",
        source=DataSource.linkedin,
        visa_status=VisaStatus.provided,
    )
    session.add(vacancy)
    session.commit()
    return vacancy


def test_submission_statuses_name_each_delivery_route():
    assert VacancyStatus.submitted_via_email.value == "submitted_via_email"
    assert VacancyStatus.submitted_via_url.value == "submitted_via_url"
    assert VacancyStatus.submitted_via_all.value == "submitted_via_all"


def test_email_then_url_marks_submission_via_all():
    engine = create_engine("sqlite:///:memory:")
    init_db(bind_engine=engine)
    session = sessionmaker(bind=engine)()
    vacancy = _vacancy(session)

    assert confirm_email_application_submitted(session, vacancy.id).status == (
        VacancyStatus.submitted_via_email
    )
    assert confirm_url_application_submitted(session, vacancy.id).status == (
        VacancyStatus.submitted_via_all
    )


def test_url_then_email_marks_submission_via_all():
    engine = create_engine("sqlite:///:memory:")
    init_db(bind_engine=engine)
    session = sessionmaker(bind=engine)()
    vacancy = _vacancy(session)

    assert confirm_url_application_submitted(session, vacancy.id).status == (
        VacancyStatus.submitted_via_url
    )
    assert confirm_email_application_submitted(session, vacancy.id).status == (
        VacancyStatus.submitted_via_all
    )


def test_submitted_via_email_can_transition_to_application_error():
    from ljpa_reworked.operations.vacancy_ops import transition_vacancy_status

    engine = create_engine("sqlite:///:memory:")
    init_db(bind_engine=engine)
    session = sessionmaker(bind=engine)()
    vacancy = _vacancy(session)

    confirm_email_application_submitted(session, vacancy.id)
    assert vacancy.status == VacancyStatus.submitted_via_email

    updated = transition_vacancy_status(
        session, vacancy.id, VacancyStatus.application_error
    )
    assert updated.status == VacancyStatus.application_error
