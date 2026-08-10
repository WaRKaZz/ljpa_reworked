from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ljpa_reworked.database import init_db
from ljpa_reworked.models.crewai_pydantic_models import VacancyCrewAI, VisaStatus
from ljpa_reworked.models.database_models import DataSource, Vacancy
from ljpa_reworked.models.enums import VacancyStatus


def test_vacancy_status_enum_values():
    assert VacancyStatus.created.value == "created"
    assert VacancyStatus.updated.value == "updated"
    assert VacancyStatus.reviewed.value == "reviewed"
    assert VacancyStatus.rejected.value == "rejected"
    assert VacancyStatus.review_error.value == "review_error"
    assert VacancyStatus.application_prepared.value == "application_prepared"
    assert VacancyStatus.applied.value == "applied"
    assert VacancyStatus.application_error.value == "application_error"
    assert VacancyStatus.withdrawn.value == "withdrawn"
    assert VacancyStatus.expired.value == "expired"
    assert VacancyStatus.archived.value == "archived"


def test_vacancy_model_status_default():
    engine = create_engine("sqlite:///:memory:")
    init_db(bind_engine=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    v = Vacancy(
        title="Test Title",
        text="Test Text",
        submit_email="test@example.com",
        source=DataSource.linkedin,
        visa_status=VisaStatus.provided,
    )
    assert not hasattr(v, "processed")
    session.add(v)
    session.commit()

    assert hasattr(v, "status")
    assert v.status == VacancyStatus.created


def test_crewai_pydantic_models_reexports_vacancystatus():
    from ljpa_reworked.models.crewai_pydantic_models import (
        VacancyStatus as CrewAIVacancyStatus,
    )

    assert CrewAIVacancyStatus is VacancyStatus


def test_crewai_task_expected_output_does_not_contain_status():
    # Verify VacancyCrewAI model fields do not include status
    assert "status" not in VacancyCrewAI.model_fields
