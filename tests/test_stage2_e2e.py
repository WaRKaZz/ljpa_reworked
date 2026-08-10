from unittest.mock import patch

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from ljpa_reworked.database import Base
from ljpa_reworked.models.crewai_pydantic_models import VisaStatus
from ljpa_reworked.models.database_models import DataSource
from ljpa_reworked.operations.vacancy_ops import (
    get_all_vacancies,
    save_vacancy,
)
from ljpa_reworked.services.jobspy import fetch_and_store_jobs


@pytest.fixture
def db_session():
    """SQLite in-memory database session fixture for Stage 2 integration tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_stage2_jobspy_integration(db_session):
    """Test full integration of fetch_and_store_jobs with mocked scrape_jobs data,
    ensuring DB records are correctly inserted into SQLite with correct fields (Vacancy model).
    """
    mock_df = pd.DataFrame([
        {
            "title": "Senior Backend Engineer",
            "company": "Tech Corp",
            "job_url": "https://www.linkedin.com/jobs/view/12345/",
            "description": "We are looking for a Senior Backend Engineer proficient in Python and SQLite.",
            "emails": "jobs@techcorp.com",
            "location": "Remote",
        }
    ])

    with patch("ljpa_reworked.services.jobspy.scrape_jobs", return_value=mock_df):
        vacancies = fetch_and_store_jobs(
            site_name="linkedin",
            search_term="Backend Engineer",
            location="Remote",
            results_wanted=5,
            db=db_session,
        )

        assert len(vacancies) == 1
        db_records = get_all_vacancies(db_session)
        assert len(db_records) == 1
        record = db_records[0]
        assert record.title == "Senior Backend Engineer"
        assert record.text == "We are looking for a Senior Backend Engineer proficient in Python and SQLite."
        assert record.credentials == "jobs@techcorp.com"
        assert record.url == "https://www.linkedin.com/jobs/view/12345/"
        assert record.source == DataSource.linkedin
        assert record.visa_status == VisaStatus.not_mentioned


def test_stage2_direct_vacancy_integration(db_session):
    """Test direct saving of vacancies into SQLite database."""
    saved = save_vacancy(
        title="Lead DevOps Engineer",
        text="Hiring Lead DevOps Engineer! Contact devops@example.com",
        url="https://www.linkedin.com/feed/update/urn:li:activity:777777/",
        credentials="devops@example.com",
        db=db_session,
    )
    assert saved.id is not None

    db_vacancies = get_all_vacancies(db_session)
    assert len(db_vacancies) == 1
    v = db_vacancies[0]
    assert v.title == "Lead DevOps Engineer"
    assert v.url == "https://www.linkedin.com/feed/update/urn:li:activity:777777/"
    assert v.deleted is False
