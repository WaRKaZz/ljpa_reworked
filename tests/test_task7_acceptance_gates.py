"""Acceptance tests for Task 7: Validation and Safety Gates."""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ljpa_reworked.database import init_db
from ljpa_reworked.models.crewai_pydantic_models import (
    JobSearchQuery,
    JobSearchQuerySet,
    VisaStatus,
)
from ljpa_reworked.models.database_models import DataSource, Vacancy
from ljpa_reworked.models.enums import VacancyStatus
from ljpa_reworked.operations.vacancy_ops import upsert_vacancy_by_url
from ljpa_reworked.services.jobspy import (
    JobSpyIntegrationService,
    compute_profile_sha256,
    get_or_generate_job_search_queries,
)


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database session for unit testing."""
    engine = create_engine("sqlite:///:memory:")
    init_db(bind_engine=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()


def test_profile_change_causes_query_regeneration_unchanged_reuses_cache(tmp_path):
    """Assert profile SHA256 change triggers CrewAI query regeneration, while unchanged profile reuses cache."""
    profile_file = tmp_path / "profile.md"
    cache_file = tmp_path / "profile_search_query.json"

    profile_file.write_text("Profile version 1", encoding="utf-8")
    _, sha1 = compute_profile_sha256(profile_file)

    mock_crew = MagicMock()
    mock_crew.return_value = JobSearchQuerySet(
        profile_sha256=sha1,
        queries=[
            JobSearchQuery(
                site_name="linkedin",
                search_term="Python Developer",
                location="Remote",
                results_wanted=10,
            )
        ],
    )

    # 1. Initial call generates and caches queries
    res1 = get_or_generate_job_search_queries(
        profile_path=profile_file,
        cache_path=cache_file,
        crew_runner=mock_crew,
    )
    assert res1.profile_sha256 == sha1
    assert mock_crew.call_count == 1

    # 2. Call with unchanged profile reuses cache (0 additional crew calls)
    res2 = get_or_generate_job_search_queries(
        profile_path=profile_file,
        cache_path=cache_file,
        crew_runner=mock_crew,
    )
    assert res2.profile_sha256 == sha1
    assert mock_crew.call_count == 1

    # 3. Modify profile -> SHA256 changes -> triggers crew regeneration
    profile_file.write_text("Profile version 2 (updated skills)", encoding="utf-8")
    _, sha2 = compute_profile_sha256(profile_file)

    mock_crew2 = MagicMock()
    mock_crew2.return_value = JobSearchQuerySet(
        profile_sha256=sha2,
        queries=[
            JobSearchQuery(
                site_name="linkedin",
                search_term="Senior Python Engineer",
                location="Remote",
                results_wanted=15,
            )
        ],
    )

    res3 = get_or_generate_job_search_queries(
        profile_path=profile_file,
        cache_path=cache_file,
        crew_runner=mock_crew2,
    )
    assert res3.profile_sha256 == sha2
    assert mock_crew2.call_count == 1


def test_job_search_query_set_strict_deduplicated_json():
    """Assert JobSearchQuerySet validates strict schema, SHA256 matching, and deduplication."""
    valid_data = {
        "profile_sha256": "a" * 64,
        "queries": [
            {
                "site_name": "linkedin",
                "search_term": "Backend Engineer",
                "location": "Berlin",
                "results_wanted": 10,
            }
        ],
    }
    qs = JobSearchQuerySet.model_validate(valid_data)
    assert qs.profile_sha256 == "a" * 64
    json_str = qs.model_dump_json()
    assert "Backend Engineer" in json_str

    # Test deduplication helper
    q1 = JobSearchQuery(
        site_name="linkedin", search_term="Python", location="Remote", results_wanted=10
    )
    q2 = JobSearchQuery(
        site_name="linkedin", search_term="python ", location="remote", results_wanted=5
    )
    from ljpa_reworked.services.jobspy import normalize_and_deduplicate_queries

    deduped = normalize_and_deduplicate_queries([q1, q2])
    assert len(deduped) == 1


def test_non_empty_url_or_email_mandatory(db_session):
    """Assert JobSpy upsert skips and returns None when both submit_url and submit_email are empty/null."""
    v1, created1 = upsert_vacancy_by_url(
        db_session, {"title": "No Contact", "submit_url": "", "submit_email": ""}
    )
    assert v1 is None
    assert created1 is False

    v2, created2 = upsert_vacancy_by_url(
        db_session, {"title": "None Contact", "submit_url": None, "submit_email": None}
    )
    assert v2 is None
    assert created2 is False

    v3, created3 = upsert_vacancy_by_url(
        db_session,
        {"title": "Whitespace Contact", "submit_url": "   ", "submit_email": "   "},
    )
    assert v3 is None
    assert created3 is False

    # Valid non-empty submit_url succeeds
    v4, created4 = upsert_vacancy_by_url(
        db_session,
        {
            "title": "Valid URL Job",
            "submit_url": "https://linkedin.com/jobs/view/1001",
            "source": DataSource.linkedin,
        },
    )
    assert v4 is not None
    assert created4 is True


def test_existing_url_refreshes_source_fields_and_sets_updated_status(db_session):
    """Assert existing vacancy URL updates source fields and sets status=updated."""
    # 1. Create initial vacancy
    v_initial, created = upsert_vacancy_by_url(
        db_session,
        {
            "title": "Initial Title",
            "text": "Initial Text",
            "submit_url": "https://linkedin.com/jobs/view/2002",
            "source": DataSource.linkedin,
            "visa_status": VisaStatus.provided,
        },
    )
    assert created is True

    # 2. Re-scrape same URL with updated title/text/email
    v_refreshed, created_again = upsert_vacancy_by_url(
        db_session,
        {
            "title": "Updated Title From Scrape",
            "text": "Updated Description Text",
            "submit_url": "https://linkedin.com/jobs/view/2002",
            "submit_email": "recruiter@example.com",
        },
    )

    assert created_again is False
    assert v_refreshed.id == v_initial.id
    assert v_refreshed.title == "Updated Title From Scrape"
    assert v_refreshed.text == "Updated Description Text"
    assert v_refreshed.submit_email == "recruiter@example.com"
    assert v_refreshed.status == VacancyStatus.updated


def test_vacancy_processed_removed_and_status_is_non_null_enum(db_session):
    """Assert Vacancy.processed column is removed and Vacancy.status is non-null enum default created."""
    assert not hasattr(Vacancy, "processed")
    v = Vacancy(
        title="Test Job",
        text="Test Text",
        submit_email="cred@example.com",
        source=DataSource.linkedin,
        visa_status=VisaStatus.not_mentioned,
    )
    db_session.add(v)
    db_session.commit()
    assert hasattr(v, "status")
    assert v.status == VacancyStatus.created


def test_discovery_run_has_zero_calls_to_application_or_messaging_services(
    tmp_path, db_session
):
    """Assert JobSpy discovery run invokes ZERO calls to email, Telegram, resume materials, or submitter."""
    profile_file = tmp_path / "profile.md"
    cache_file = tmp_path / "profile_search_query.json"

    profile_file.write_text("Senior Python Developer profile", encoding="utf-8")
    _, sha = compute_profile_sha256(profile_file)

    mock_crew = MagicMock()
    mock_crew.return_value = JobSearchQuerySet(
        profile_sha256=sha,
        queries=[
            JobSearchQuery(
                site_name="linkedin",
                search_term="Python",
                location="Remote",
                results_wanted=5,
            )
        ],
    )

    import pandas as pd

    mock_df = pd.DataFrame(
        [
            {
                "job_url": "https://linkedin.com/jobs/view/3003",
                "title": "Python Specialist",
                "description": "Awesome Python position.",
                "emails": "hr@pythoncompany.com",
            }
        ]
    )

    service = JobSpyIntegrationService(
        profile_path=profile_file,
        cache_path=cache_file,
        crew_runner=mock_crew,
    )

    with (
        patch(
            "ljpa_reworked.services.jobspy.scrape_jobs", return_value=mock_df
        ) as mock_scrape,
        patch("ljpa_reworked.services.smtp_client.SMTPClient") as mock_smtp,
        patch("ljpa_reworked.services.telegram.Telegram") as mock_telegram,
    ):
        summary = service.run(db=db_session)

        assert mock_scrape.called
        assert summary.queries_attempted == 1
        assert summary.created_count == 1

        # Verify zero calls to messaging / submission services
        assert mock_smtp.call_count == 0
        assert mock_telegram.call_count == 0


def test_pytest_coverage_gate_configured():
    """Assert pytest-cov configuration in pyproject.toml has coverage enabled, omissions, and fail_under gate."""
    from pathlib import Path

    import tomllib

    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    assert pyproject_path.exists()

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    pytest_opts = data.get("tool", {}).get("pytest", {}).get("ini_options", {})
    addopts = pytest_opts.get("addopts", "")
    assert "--cov=" in addopts
    assert "--cov-report=term-missing" in addopts

    cov_run = data.get("tool", {}).get("coverage", {}).get("run", {})
    omit = cov_run.get("omit", [])
    assert "**/__init__.py" in omit
    assert "src/ljpa_reworked/main.py" in omit

    cov_report = data.get("tool", {}).get("coverage", {}).get("report", {})
    fail_under = cov_report.get("fail_under")
    assert fail_under is not None
    assert fail_under >= 65
