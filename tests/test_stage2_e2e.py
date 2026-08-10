from unittest.mock import AsyncMock, MagicMock, patch
import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from ljpa_reworked.database import Base
from ljpa_reworked.models.database_models import DataSource, LinkedinPost, Vacancy
from ljpa_reworked.models.crewai_pydantic_models import VisaStatus
from ljpa_reworked.services.jobspy import fetch_and_store_jobs
from ljpa_reworked.operations.linkedin_post_ops import (
    get_all_linkedin_posts,
    link_post_to_vacancy,
    save_linkedin_post,
)
from ljpa_reworked.operations.vacancy_ops import get_all_vacancies


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


def test_stage2_posts_scraper_integration(db_session):
    """Test integration of run_agy_harness_1 and save_linkedin_post,
    verifying LinkedinPost models are persisted correctly into SQLite.
    """
    saved_post = save_linkedin_post(
        text="Hiring Lead DevOps Engineer! Contact devops@example.com",
        url="https://www.linkedin.com/feed/update/urn:li:activity:777777/",
        db=db_session,
    )
    assert saved_post.id is not None

    db_posts = get_all_linkedin_posts(db_session)
    assert len(db_posts) == 1
    post_record = db_posts[0]
    assert post_record.text == "Hiring Lead DevOps Engineer! Contact devops@example.com"
    assert post_record.url == "https://www.linkedin.com/feed/update/urn:li:activity:777777/"
    assert post_record.processed is False
    assert post_record.deleted is False


def test_stage2_combined_collection_pipeline(db_session):
    """Test executing both collection pipelines together, verifying distinct models
    (Vacancy and LinkedinPost) co-exist in SQLite database without collision.
    """
    mock_df = pd.DataFrame([
        {
            "title": "Full Stack Developer",
            "company": "Web Solutions",
            "job_url": "https://www.linkedin.com/jobs/view/55555/",
            "description": "Looking for Full Stack Developer with React and Python experience.",
            "emails": "careers@websolutions.com",
            "location": "Hybrid",
        },
        {
            "title": "Data Scientist",
            "company": "Data AI",
            "job_url": "https://www.linkedin.com/jobs/view/66666/",
            "description": "Data Scientist with PyTorch & SQL skills.",
            "emails": "hr@dataai.com",
            "location": "Remote",
        },
    ])

    with patch("ljpa_reworked.services.jobspy.scrape_jobs", return_value=mock_df):
        jobspy_vacancies = fetch_and_store_jobs(
            site_name="linkedin",
            search_term="Developer",
            location="Remote",
            results_wanted=2,
            db=db_session,
        )
        assert len(jobspy_vacancies) == 2

    post1 = save_linkedin_post(
        text="Urgently hiring Senior QA Engineer! Send CV to qa@company.com",
        url="https://www.linkedin.com/feed/update/urn:li:activity:888888/",
        db=db_session,
    )
    post2 = save_linkedin_post(
        text="Looking for Product Manager in Berlin.",
        url="https://www.linkedin.com/feed/update/urn:li:activity:999999/",
        db=db_session,
    )

    vacancies_in_db = get_all_vacancies(db_session)
    posts_in_db = get_all_linkedin_posts(db_session)

    assert len(vacancies_in_db) == 2
    assert len(posts_in_db) == 2

    # Verify model co-existence and relationship linkage without collision
    linked_post = link_post_to_vacancy(db_session, post_id=post1.id, vacancy_id=vacancies_in_db[0].id)
    assert linked_post is not None
    assert linked_post.vacancy_id == vacancies_in_db[0].id
