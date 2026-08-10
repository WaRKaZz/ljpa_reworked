import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from ljpa_reworked.database import init_db
from ljpa_reworked.models.crewai_pydantic_models import VacancyCrewAI, VisaStatus
from ljpa_reworked.models.database_models import DataSource, Vacancy
from ljpa_reworked.models.enums import VacancyStatus
from ljpa_reworked.operations.vacancy_ops import (
    create_vacancy_direct,
    upsert_vacancy_by_url,
)


@pytest.fixture
def in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    init_db(bind_engine=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_vacancy_model_has_no_legacy_fields():
    assert not hasattr(Vacancy, "credentials")
    assert not hasattr(Vacancy, "url")
    assert hasattr(Vacancy, "submit_email")
    assert hasattr(Vacancy, "submit_url")


def test_vacancy_accepts_email_only(in_memory_db):
    v = create_vacancy_direct(
        db=in_memory_db,
        title="Backend Engineer",
        text="Job description",
        submit_email="recruiter@tech.com",
        submit_url=None,
    )
    assert v.id is not None
    assert v.submit_email == "recruiter@tech.com"
    assert v.submit_url is None


def test_vacancy_accepts_url_only(in_memory_db):
    v = create_vacancy_direct(
        db=in_memory_db,
        title="Frontend Engineer",
        text="Job description",
        submit_email=None,
        submit_url="https://careers.example.com/job/456",
    )
    assert v.id is not None
    assert v.submit_email is None
    assert v.submit_url == "https://careers.example.com/job/456"


def test_vacancy_accepts_both_contacts(in_memory_db):
    v = create_vacancy_direct(
        db=in_memory_db,
        title="Fullstack Lead",
        text="Job description",
        submit_email="hr@example.com",
        submit_url="https://careers.example.com/job/789",
    )
    assert v.id is not None
    assert v.submit_email == "hr@example.com"
    assert v.submit_url == "https://careers.example.com/job/789"


def test_vacancy_rejects_neither_contact_in_db(in_memory_db):
    with pytest.raises((IntegrityError, ValueError)):
        v = Vacancy(
            title="No Contact Job",
            text="Text",
            submit_email=None,
            submit_url=None,
            source=DataSource.linkedin,
            visa_status=VisaStatus.not_mentioned,
        )
        in_memory_db.add(v)
        in_memory_db.commit()


def test_vacancy_rejects_blank_contacts_in_db(in_memory_db):
    with pytest.raises((IntegrityError, ValueError)):
        v = Vacancy(
            title="Blank Contact Job",
            text="Text",
            submit_email="   ",
            submit_url="",
            source=DataSource.linkedin,
            visa_status=VisaStatus.not_mentioned,
        )
        in_memory_db.add(v)
        in_memory_db.commit()


def test_pydantic_rejects_invalid_nonempty_email():
    with pytest.raises(ValidationError):
        VacancyCrewAI(
            title="Dev",
            text="Text",
            submit_email="not-an-email",
            submit_url=None,
            visa_status=VisaStatus.not_mentioned,
        )


def test_pydantic_rejects_neither_contact_method():
    with pytest.raises(ValidationError):
        VacancyCrewAI(
            title="Dev",
            text="Text",
            submit_email=None,
            submit_url=None,
            visa_status=VisaStatus.not_mentioned,
        )

    with pytest.raises(ValidationError):
        VacancyCrewAI(
            title="Dev",
            text="Text",
            submit_email="   ",
            submit_url="",
            visa_status=VisaStatus.not_mentioned,
        )


def test_pydantic_normalizes_blank_strings_to_none():
    v = VacancyCrewAI(
        title="Dev",
        text="Text",
        submit_email="   ",
        submit_url="https://example.com/apply",
        visa_status=VisaStatus.not_mentioned,
    )
    assert v.submit_email is None
    assert v.submit_url == "https://example.com/apply"


def test_url_upsert_uses_submit_url(in_memory_db):
    data = {
        "title": "Data Engineer",
        "text": "Job details",
        "submit_email": "jobs@data.com",
        "submit_url": "https://data.com/jobs/1",
    }
    vac, created = upsert_vacancy_by_url(in_memory_db, data)
    assert created is True
    assert vac.submit_url == "https://data.com/jobs/1"
    assert vac.submit_email == "jobs@data.com"
    assert vac.status == VacancyStatus.created

    # Update with existing submit_url
    data_update = {
        "title": "Senior Data Engineer",
        "text": "Updated details",
        "submit_email": "newjobs@data.com",
        "submit_url": "https://data.com/jobs/1",
    }
    vac_refreshed, created_again = upsert_vacancy_by_url(in_memory_db, data_update)
    assert created_again is False
    assert vac_refreshed.id == vac.id
    assert vac_refreshed.title == "Senior Data Engineer"
    assert vac_refreshed.submit_email == "newjobs@data.com"
    assert vac_refreshed.status == VacancyStatus.updated


def test_fresh_bootstrap_schema_without_alembic(in_memory_db):
    from sqlalchemy import inspect

    inspector = inspect(in_memory_db.bind)
    tables = inspector.get_table_names()
    assert "vacancy" in tables
    columns = [c["name"] for c in inspector.get_columns("vacancy")]
    assert "submit_email" in columns
    assert "submit_url" in columns
    assert "credentials" not in columns
    assert "url" not in columns
