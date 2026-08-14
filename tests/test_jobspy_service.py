from unittest.mock import MagicMock, patch

import pandas as pd

from ljpa_reworked.services.jobspy import (
    fetch_and_store_jobs,
    validate_jobspy_query,
)


@patch("ljpa_reworked.services.jobspy.scrape_jobs")
@patch("ljpa_reworked.services.jobspy.upsert_vacancy_by_url")
def test_fetch_and_store_jobs_service(mock_upsert_vacancy_by_url, mock_scrape_jobs):
    mock_df = pd.DataFrame(
        [
            {
                "title": "Python Developer",
                "description": "Great job description",
                "job_url": "https://linkedin.com/jobs/view/123",
                "emails": "hr@example.com",
            }
        ]
    )
    mock_scrape_jobs.return_value = mock_df
    mock_upsert_vacancy_by_url.return_value = (
        MagicMock(id=1, title="Python Developer"),
        True,
    )

    db_mock = MagicMock()
    result = fetch_and_store_jobs(search_term="Python Developer", db=db_mock)

    assert len(result) == 1
    mock_scrape_jobs.assert_called_once()
    mock_upsert_vacancy_by_url.assert_called_once()


@patch("ljpa_reworked.services.jobspy.scrape_jobs")
def test_fetch_and_store_jobs_skips_glassdoor_worldwide(mock_scrape_jobs):
    db_mock = MagicMock()
    result = fetch_and_store_jobs(
        site_name="glassdoor",
        search_term="Python Developer",
        location="worldwide",
        db=db_mock,
    )
    assert result == []
    mock_scrape_jobs.assert_not_called()


def test_validate_jobspy_query_disables_ziprecruiter():
    reason = validate_jobspy_query("zip_recruiter", "Remote")
    assert reason is not None
    assert "ziprecruiter" in reason.lower() or "unavailable" in reason.lower()

    reason_alt = validate_jobspy_query("ziprecruiter", "Remote")
    assert reason_alt is not None


@patch("ljpa_reworked.services.jobspy.scrape_jobs")
def test_fetch_and_store_jobs_skips_ziprecruiter(mock_scrape_jobs):
    db_mock = MagicMock()
    result = fetch_and_store_jobs(
        site_name="zip_recruiter",
        search_term="Python Developer",
        location="Remote",
        db=db_mock,
    )
    assert result == []
    mock_scrape_jobs.assert_not_called()


@patch("ljpa_reworked.services.jobspy.scrape_jobs")
@patch("ljpa_reworked.services.jobspy.upsert_vacancy_by_url")
def test_jobspy_service_run_executes_supported_sources(mock_upsert, mock_scrape_jobs):
    from ljpa_reworked.models.crewai_pydantic_models import (
        JobSearchQuery,
        JobSearchQuerySet,
    )
    from ljpa_reworked.services.jobspy import JobSpyIntegrationService

    mock_scrape_jobs.return_value = pd.DataFrame(
        [
            {
                "title": "Python Developer",
                "description": "Desc",
                "job_url": "https://linkedin.com/jobs/1",
            }
        ]
    )
    mock_upsert.return_value = (MagicMock(), True)

    query_set = JobSearchQuerySet(
        profile_sha256="a" * 64,
        queries=[
            JobSearchQuery(
                search_term="Python Developer", location="Remote", site_name="linkedin"
            ),
            JobSearchQuery(
                search_term="Python Developer",
                location="Munich, Germany",
                site_name="indeed",
            ),
        ],
    )
    service = JobSpyIntegrationService(crew_runner=MagicMock(return_value=query_set))

    with patch(
        "ljpa_reworked.services.jobspy.load_cached_queries", return_value=query_set
    ):
        summary = service.run(db=MagicMock())

    assert summary.queries_attempted == 2
    assert [call.kwargs["site_name"] for call in mock_scrape_jobs.call_args_list] == [
        ["linkedin"],
        ["indeed"],
    ]
    assert mock_scrape_jobs.call_args_list[1].kwargs["country_indeed"] == "germany"


def test_indeed_country_follows_query_location():
    from ljpa_reworked.services.jobspy import indeed_country_for_location

    assert indeed_country_for_location("Houston, TX, USA") == "usa"
    assert indeed_country_for_location("Frankfurt, Germany") == "germany"
    assert indeed_country_for_location("Dubai, UAE") == "united arab emirates"
