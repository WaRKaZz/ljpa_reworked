from unittest.mock import MagicMock, patch
import pandas as pd
import pytest

from ljpa_reworked.models.database_models import DataSource, Vacancy
from ljpa_reworked.models.crewai_pydantic_models import VisaStatus
from ljpa_reworked.operations.vacancy_ops import save_vacancy


def test_fetch_and_store_jobs_normalizes_and_saves():
    from ljpa_reworked.services.harness_jobspy import fetch_and_store_jobs

    mock_df = pd.DataFrame([
        {
            "title": "Senior Python Engineer",
            "company": "Tech Corp",
            "job_url": "https://www.linkedin.com/jobs/view/99999/",
            "description": "Looking for Senior Python Engineer with 5+ years experience.",
            "emails": "recruiter@techcorp.com",
            "location": "Remote",
        }
    ])

    mock_vacancy = Vacancy(
        id=1,
        title="Senior Python Engineer",
        text="Looking for Senior Python Engineer with 5+ years experience.",
        credentials="recruiter@techcorp.com",
        url="https://www.linkedin.com/jobs/view/99999/",
        source=DataSource.linkedin,
        visa_status=VisaStatus.not_mentioned,
    )

    with patch("ljpa_reworked.services.harness_jobspy.scrape_jobs", return_value=mock_df) as mock_scrape, \
         patch("ljpa_reworked.services.harness_jobspy.save_vacancy", return_value=mock_vacancy) as mock_save:
        
        results = fetch_and_store_jobs(
            site_name="linkedin",
            search_term="Python Engineer",
            location="Remote",
            results_wanted=5,
        )

        mock_scrape.assert_called_once_with(
            site_name=["linkedin"],
            search_term="Python Engineer",
            location="Remote",
            results_wanted=5,
            hours_old=72,
        )
        mock_save.assert_called_once_with(
            title="Senior Python Engineer",
            text="Looking for Senior Python Engineer with 5+ years experience.",
            credentials="recruiter@techcorp.com",
            url="https://www.linkedin.com/jobs/view/99999/",
            source=DataSource.linkedin,
            visa_status=VisaStatus.not_mentioned,
            db=None,
        )
        assert len(results) == 1
        assert results[0] == mock_vacancy


def test_fetch_and_store_jobs_empty_dataframe():
    from ljpa_reworked.services.harness_jobspy import fetch_and_store_jobs

    empty_df = pd.DataFrame()

    with patch("ljpa_reworked.services.harness_jobspy.scrape_jobs", return_value=empty_df):
        results = fetch_and_store_jobs(
            site_name="linkedin",
            search_term="Python",
            location="Remote",
            results_wanted=10,
        )
        assert results == []


def test_save_vacancy_operation():
    mock_db = MagicMock()
    mock_vacancy = MagicMock()

    with patch("ljpa_reworked.operations.vacancy_ops.create_vacancy_direct", return_value=mock_vacancy) as mock_create:
        res = save_vacancy(
            title="Test Title",
            text="Test Description",
            credentials="test@example.com",
            url="https://example.com/job/1",
            source=DataSource.linkedin,
            visa_status=VisaStatus.not_mentioned,
            db=mock_db,
        )
        mock_create.assert_called_once_with(
            db=mock_db,
            title="Test Title",
            text="Test Description",
            credentials="test@example.com",
            url="https://example.com/job/1",
            source=DataSource.linkedin,
            visa_status=VisaStatus.not_mentioned,
        )
        assert res == mock_vacancy
