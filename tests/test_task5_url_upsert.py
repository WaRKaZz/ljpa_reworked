from unittest.mock import patch

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ljpa_reworked.database import Base
from ljpa_reworked.models.crewai_pydantic_models import VisaStatus
from ljpa_reworked.models.database_models import BasicEvaluation, DataSource, Vacancy
from ljpa_reworked.models.enums import VacancyStatus
from ljpa_reworked.operations.vacancy_ops import (
    get_vacancy_by_id,
    transition_vacancy_status,
    upsert_vacancy_by_url,
)
from ljpa_reworked.services.jobspy import fetch_and_store_jobs


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_create_vacancy_on_first_url_scrape(db):
    data = {
        "title": "Python Engineer",
        "text": "Job details text",
        "credentials": "contact@example.com",
        "url": "https://example.com/jobs/123",
        "source": DataSource.linkedin,
        "visa_status": VisaStatus.provided,
    }
    vacancy, is_created = upsert_vacancy_by_url(db, data)
    assert is_created is True
    assert vacancy is not None
    assert vacancy.id is not None
    assert vacancy.title == "Python Engineer"
    assert vacancy.text == "Job details text"
    assert vacancy.url == "https://example.com/jobs/123"
    assert vacancy.status == VacancyStatus.created


def test_refresh_source_owned_fields_on_second_scrape(db):
    data1 = {
        "title": "Original Title",
        "text": "Original text",
        "credentials": "old@example.com",
        "url": "https://example.com/jobs/456",
        "source": DataSource.linkedin,
        "visa_status": VisaStatus.not_mentioned,
    }
    vac1, created1 = upsert_vacancy_by_url(db, data1)
    assert created1 is True
    vac1_id = vac1.id

    data2 = {
        "title": "Updated Title",
        "text": "Updated description",
        "credentials": "new@example.com",
        "url": "https://example.com/jobs/456",
        "source": DataSource.other,
        "visa_status": VisaStatus.provided,
    }
    vac2, created2 = upsert_vacancy_by_url(db, data2)
    assert created2 is False
    assert vac2.id == vac1_id
    assert vac2.title == "Updated Title"
    assert vac2.text == "Updated description"
    assert vac2.credentials == "new@example.com"
    assert vac2.source == DataSource.other
    assert vac2.visa_status == VisaStatus.provided


def test_preserve_workflow_data_and_status_on_refresh(db):
    data = {
        "title": "Backend Dev",
        "text": "Python job",
        "credentials": "hr@corp.com",
        "url": "https://example.com/jobs/789",
        "source": DataSource.linkedin,
        "visa_status": VisaStatus.not_mentioned,
    }
    vac, _ = upsert_vacancy_by_url(db, data)
    vac_id = vac.id
    original_created_at = vac.created_at

    # Mutate workflow state: change status to applied and attach basic_evaluation
    transition_vacancy_status(db, vac_id, VacancyStatus.applied)

    evaluation = BasicEvaluation(summary="Great match", rating=85, vacancy_id=vac_id)
    db.add(evaluation)
    db.commit()

    # Re-scrape same URL with updated job info
    data_scrape2 = {
        "title": "Backend Dev (Updated)",
        "text": "Python job with more details",
        "credentials": "hr@corp.com",
        "url": "https://example.com/jobs/789",
        "source": DataSource.linkedin,
        "visa_status": VisaStatus.provided,
    }
    vac_refreshed, created = upsert_vacancy_by_url(db, data_scrape2)
    assert created is False
    assert vac_refreshed.id == vac_id
    assert vac_refreshed.status == VacancyStatus.applied
    assert vac_refreshed.title == "Backend Dev (Updated)"
    assert vac_refreshed.created_at == original_created_at

    # Check evaluation relationship preserved
    reloaded = get_vacancy_by_id(db, vac_id)
    assert reloaded.basic_evaluation is not None
    assert reloaded.basic_evaluation.rating == 85
    assert reloaded.basic_evaluation.summary == "Great match"


def test_skip_missing_or_empty_url(db):
    res1, created1 = upsert_vacancy_by_url(db, {"title": "No URL", "url": None})
    assert res1 is None
    assert created1 is False

    res2, created2 = upsert_vacancy_by_url(db, {"title": "Empty URL", "url": "   "})
    assert res2 is None
    assert created2 is False

    assert db.query(Vacancy).count() == 0


def test_repeated_same_url_in_single_scrape_batch(db):
    mock_jobs_data = pd.DataFrame(
        [
            {
                "title": "Job 1",
                "description": "Desc 1",
                "emails": "email1@test.com",
                "job_url": "https://example.com/jobs/duplicate",
            },
            {
                "title": "Job 1 Duplicate",
                "description": "Desc 1 Dup",
                "emails": "email1@test.com",
                "job_url": "https://example.com/jobs/duplicate",
            },
            {
                "title": "Job 1 Duplicate 2",
                "description": "Desc 1 Dup 2",
                "emails": "email1@test.com",
                "job_url": " https://example.com/jobs/duplicate ",  # extra spaces
            },
            {
                "title": "Job 2 Unique",
                "description": "Desc 2",
                "emails": "email2@test.com",
                "job_url": "https://example.com/jobs/unique",
            },
            {
                "title": "Job No URL",
                "description": "No URL job",
                "emails": "",
                "job_url": "  ",
            },
        ]
    )

    with patch("ljpa_reworked.services.jobspy.scrape_jobs", return_value=mock_jobs_data):
        vacancies = fetch_and_store_jobs(
            site_name="linkedin",
            search_term="Python",
            location="Remote",
            results_wanted=10,
            db=db,
        )

    # 2 unique non-empty URLs processed -> 2 vacancies in return list and DB
    assert len(vacancies) == 2
    assert db.query(Vacancy).count() == 2

    urls_in_db = {v.url for v in db.query(Vacancy).all()}
    assert urls_in_db == {
        "https://example.com/jobs/duplicate",
        "https://example.com/jobs/unique",
    }
