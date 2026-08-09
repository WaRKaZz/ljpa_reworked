from unittest.mock import MagicMock, patch
import pandas as pd
from ljpa_reworked.services.jobspy import fetch_and_store_jobs

@patch("ljpa_reworked.services.jobspy.scrape_jobs")
@patch("ljpa_reworked.services.jobspy.save_vacancy")
def test_fetch_and_store_jobs_service(mock_save_vacancy, mock_scrape_jobs):
    mock_df = pd.DataFrame([{
        "title": "Python Developer",
        "description": "Great job description",
        "job_url": "https://linkedin.com/jobs/view/123",
        "emails": "hr@example.com",
    }])
    mock_scrape_jobs.return_value = mock_df
    mock_save_vacancy.return_value = MagicMock(id=1, title="Python Developer")

    db_mock = MagicMock()
    result = fetch_and_store_jobs(search_term="Python Developer", db=db_mock)

    assert len(result) == 1
    mock_scrape_jobs.assert_called_once()
