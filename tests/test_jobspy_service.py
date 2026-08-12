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
