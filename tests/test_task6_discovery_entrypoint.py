import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ljpa_reworked.models.database_models import Base, Vacancy
from ljpa_reworked.models.crewai_pydantic_models import JobSearchQuery
from ljpa_reworked.services.jobspy import (
    JobSpyIntegrationService,
    JobSpyDiscoveryRunSummary,
)
from ljpa_reworked.main import run_jobspy_discovery


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_jobspy_discovery_run_counters(db_session):
    queries = [
        JobSearchQuery(
            site_name="linkedin",
            search_term="Python Engineer",
            location="Remote",
            results_wanted=5,
        ),
        JobSearchQuery(
            site_name="indeed",
            search_term="Backend Engineer",
            location="Remote",
            results_wanted=5,
        ),
    ]

    df_q1 = pd.DataFrame([
        {
            "title": "Python Dev 1",
            "description": "desc 1",
            "emails": "dev1@test.com",
            "job_url": "https://linkedin.com/jobs/1",
        },
        {
            "title": "Python Dev 2",
            "description": "desc 2",
            "emails": None,
            "job_url": "https://linkedin.com/jobs/2",
        },
        {
            "title": "Python Dev No URL",
            "description": "desc 3",
            "emails": None,
            "job_url": "",
        },
    ])

    df_q2 = pd.DataFrame([
        {
            "title": "Backend Dev 1 Refreshed",
            "description": "desc 1 updated",
            "emails": "dev1@test.com",
            "job_url": "https://linkedin.com/jobs/1",
        },
        {
            "title": "Backend Dev 3",
            "description": "desc 4",
            "emails": None,
            "job_url": "https://linkedin.com/jobs/3",
        },
    ])

    def mock_scrape_jobs(site_name, search_term, location, results_wanted, hours_old=72):
        if search_term == "Python Engineer":
            return df_q1
        return df_q2

    service = JobSpyIntegrationService()

    with patch.object(service, "get_queries", return_value=queries):
        with patch("ljpa_reworked.services.jobspy.scrape_jobs", side_effect=mock_scrape_jobs):
            summary = service.run(db=db_session)

    assert isinstance(summary, JobSpyDiscoveryRunSummary)
    assert summary.queries_attempted == 2
    assert summary.rows_received == 5
    assert summary.created_count == 3
    assert summary.refreshed_count == 1
    assert summary.skipped_without_url_count == 1
    assert len(summary.failures_by_query) == 0

    vacancies = db_session.query(Vacancy).all()
    assert len(vacancies) == 3


def test_jobspy_discovery_handles_query_failure(db_session):
    queries = [
        JobSearchQuery(
            site_name="linkedin",
            search_term="Failed Query",
            location="Remote",
            results_wanted=5,
        ),
        JobSearchQuery(
            site_name="indeed",
            search_term="Success Query",
            location="Remote",
            results_wanted=5,
        ),
    ]

    df_success = pd.DataFrame([
        {
            "title": "Success Dev",
            "description": "desc",
            "emails": None,
            "job_url": "https://indeed.com/jobs/99",
        }
    ])

    def mock_scrape_jobs(site_name, search_term, location, results_wanted, hours_old=72):
        if search_term == "Failed Query":
            raise RuntimeError("JobSpy connection failed")
        return df_success

    service = JobSpyIntegrationService()

    with patch.object(service, "get_queries", return_value=queries):
        with patch("ljpa_reworked.services.jobspy.scrape_jobs", side_effect=mock_scrape_jobs):
            summary = service.run(db=db_session)

    assert summary.queries_attempted == 2
    assert summary.rows_received == 1
    assert summary.created_count == 1
    assert summary.refreshed_count == 0
    assert summary.skipped_without_url_count == 0
    assert len(summary.failures_by_query) == 1
    assert "JobSpy connection failed" in summary.failures_by_query[0]["error"]


def test_discovery_entrypoint_is_strictly_discovery_only(db_session):
    queries = [
        JobSearchQuery(
            site_name="linkedin",
            search_term="Python Engineer",
            location="Remote",
            results_wanted=5,
        )
    ]
    df = pd.DataFrame([
        {
            "title": "Python Dev",
            "description": "desc",
            "emails": None,
            "job_url": "https://linkedin.com/jobs/100",
        }
    ])

    with patch("ljpa_reworked.services.jobspy.JobSpyIntegrationService.get_queries", return_value=queries):
        with patch("ljpa_reworked.services.jobspy.scrape_jobs", return_value=df):
            with patch("ljpa_reworked.crew_workflow.crewai_evaluate_vacancy") as mock_eval, \
                 patch("ljpa_reworked.crew_workflow.crewai_generate_resume") as mock_resume, \
                 patch("ljpa_reworked.crew_workflow.crewai_generate_email") as mock_email, \
                 patch("ljpa_reworked.workflow.send_telegram_post") as mock_telegram, \
                 patch("ljpa_reworked.workflow.send_email") as mock_send_email:

                summary = run_jobspy_discovery(db=db_session)

                assert summary.created_count == 1
                assert mock_eval.call_count == 0
                assert mock_resume.call_count == 0
                assert mock_email.call_count == 0
                assert mock_telegram.call_count == 0
                assert mock_send_email.call_count == 0
