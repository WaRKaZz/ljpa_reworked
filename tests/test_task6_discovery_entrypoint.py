from unittest.mock import patch

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ljpa_reworked.models.crewai_pydantic_models import JobSearchQuery
from ljpa_reworked.models.database_models import Base, Vacancy
from ljpa_reworked.services.jobspy import (
    JobSpyIntegrationService,
    JobSpyRunSummary,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_jobspy_search_run_counters(db_session):
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

    df_q1 = pd.DataFrame(
        [
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
        ]
    )

    df_q2 = pd.DataFrame(
        [
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
        ]
    )

    def mock_scrape_jobs(
        site_name,
        search_term,
        location,
        results_wanted,
        hours_old=72,
        country_indeed="worldwide",
    ):
        if search_term == "Python Engineer":
            return df_q1
        return df_q2

    service = JobSpyIntegrationService()

    with patch.object(service, "get_queries", return_value=queries):
        with patch(
            "ljpa_reworked.services.jobspy.scrape_jobs", side_effect=mock_scrape_jobs
        ):
            summary = service.run(db=db_session)

    assert isinstance(summary, JobSpyRunSummary)
    assert summary.queries_attempted == 2
    assert summary.rows_received == 5
    assert summary.created_count == 3
    assert summary.refreshed_count == 1
    assert summary.skipped_without_url_count == 1
    assert len(summary.failures_by_query) == 0

    vacancies = db_session.query(Vacancy).all()
    assert len(vacancies) == 3


def test_jobspy_search_handles_query_failure(db_session):
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

    df_success = pd.DataFrame(
        [
            {
                "title": "Success Dev",
                "description": "desc",
                "emails": None,
                "job_url": "https://indeed.com/jobs/99",
            }
        ]
    )

    def mock_scrape_jobs(
        site_name,
        search_term,
        location,
        results_wanted,
        hours_old=72,
        country_indeed="worldwide",
    ):
        if search_term == "Failed Query":
            raise RuntimeError("JobSpy connection failed")
        return df_success

    service = JobSpyIntegrationService()

    with patch.object(service, "get_queries", return_value=queries):
        with patch(
            "ljpa_reworked.services.jobspy.scrape_jobs", side_effect=mock_scrape_jobs
        ):
            summary = service.run(db=db_session)

    assert summary.queries_attempted == 2
    assert summary.rows_received == 1
    assert summary.created_count == 1
    assert summary.refreshed_count == 0
    assert summary.skipped_without_url_count == 0
    assert len(summary.failures_by_query) == 1
    assert "JobSpy connection failed" in summary.failures_by_query[0]["error"]


def test_main_runs_jobspy_after_linkedin_harness_before_evaluation():
    from ljpa_reworked import main as main_module

    events = []
    with (
        patch.object(
            main_module,
            "run_linkedin_harness",
            side_effect=lambda: events.append("harness"),
        ),
        patch.object(main_module, "JobSpyIntegrationService") as service_class,
        patch.object(main_module, "get_eligble_vacancies", return_value=[]),
    ):
        service_class.return_value.run.side_effect = lambda: events.append("jobspy")

        main_module.main()

    assert events == ["harness", "jobspy"]


def test_jobspy_glassdoor_worldwide_query_skipped(db_session):
    queries = [
        JobSearchQuery(
            site_name="glassdoor",
            search_term="Python Engineer",
            location="worldwide",
            results_wanted=5,
        ),
    ]

    service = JobSpyIntegrationService()

    with patch.object(service, "get_queries", return_value=queries):
        with patch("ljpa_reworked.services.jobspy.scrape_jobs") as mock_scrape:
            summary = service.run(db=db_session)

    mock_scrape.assert_not_called()
    assert summary.queries_attempted == 1
    assert len(summary.failures_by_query) == 1
    assert summary.failures_by_query[0]["query"]["site_name"] == "glassdoor"
    assert summary.failures_by_query[0]["query"]["location"] == "worldwide"
    assert "glassdoor" in summary.failures_by_query[0]["error"].lower()
    assert "worldwide" in summary.failures_by_query[0]["error"].lower()


def test_jobspy_ziprecruiter_disabled_recorded_in_failures(db_session):
    queries = [
        JobSearchQuery(
            site_name="zip_recruiter",
            search_term="Backend Engineer",
            location="worldwide",
            results_wanted=5,
        ),
    ]

    service = JobSpyIntegrationService()

    with patch.object(service, "get_queries", return_value=queries):
        with patch("ljpa_reworked.services.jobspy.scrape_jobs") as mock_scrape:
            summary = service.run(db=db_session)

    mock_scrape.assert_not_called()
    assert summary.queries_attempted == 1
    assert len(summary.failures_by_query) == 1
    failure = summary.failures_by_query[0]
    assert failure["query"]["site_name"] == "zip_recruiter"
    assert failure["query"]["search_term"] == "Backend Engineer"
    assert failure["query"]["location"] == "worldwide"
    assert (
        "ziprecruiter" in failure["error"].lower()
        or "unavailable" in failure["error"].lower()
    )
