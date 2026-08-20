from unittest.mock import mock_open, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ljpa_reworked.database import Base
from ljpa_reworked.models.crewai_pydantic_models import VisaStatus
from ljpa_reworked.models.database_models import DataSource, Vacancy
from ljpa_reworked.models.enums import VacancyStatus
from ljpa_reworked.services.chatgpt_gdrive import (
    ChatGPTGDriveService,
    ChatGPTJobItem,
    fetch_gdrive_json_data,
    parse_and_validate_vacancies,
    sync_chatgpt_vacancies_to_db,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_chatgpt_job_item_validation_success():
    item = ChatGPTJobItem.model_validate(
        {
            "title": "Controls Engineer",
            "company": "Automated Inc",
            "location": "Dallas, TX",
            "text": "Full job description with responsibilities and requirements.",
            "submit_url": "https://careers.automated.com/job/1",
            "submit_email": "jobs@automated.com",
            "visa_status": "provided",
        }
    )
    assert item.title == "Controls Engineer"
    assert item.company == "Automated Inc"
    assert item.visa_status == VisaStatus.provided
    assert item.submit_url == "https://careers.automated.com/job/1"
    assert item.submit_email == "jobs@automated.com"


def test_chatgpt_job_item_boolean_visa_status():
    item_true = ChatGPTJobItem.model_validate(
        {
            "title": "Robotics Engineer",
            "text": "Valid requirements description for test.",
            "submit_url": "https://example.com/apply",
            "visa_status": True,
        }
    )
    assert item_true.visa_status == VisaStatus.provided

    item_false = ChatGPTJobItem.model_validate(
        {
            "title": "Robotics Engineer",
            "text": "Valid requirements description for test.",
            "submit_url": "https://example.com/apply",
            "visa_status": False,
        }
    )
    assert item_false.visa_status == VisaStatus.not_provided


def test_chatgpt_job_item_requires_at_least_one_contact():
    with pytest.raises(ValueError, match="at least one valid contact method"):
        ChatGPTJobItem.model_validate(
            {
                "title": "Software Engineer",
                "text": "Full job description text without contacts.",
            }
        )


def test_chatgpt_job_item_invalid_email_fails():
    with pytest.raises(ValueError, match="Invalid email syntax"):
        ChatGPTJobItem.model_validate(
            {
                "title": "Software Engineer",
                "text": "Full job description text.",
                "submit_email": "invalid-email-address",
            }
        )


def test_parse_and_validate_vacancies_filters_invalids():
    raw_payload = {
        "updated_at": "2026-08-18T09:00:00Z",
        "vacancies": [
            {
                "title": "Good Job",
                "text": "Detailed description of responsibilities.",
                "submit_url": "https://example.com/good",
                "visa_status": "provided",
            },
            {
                "title": "Bad Job (No contact)",
                "text": "Missing contact URL and email.",
            },
            {
                "title": "Another Good Job",
                "text": "Detailed description of responsibilities.",
                "submit_email": "contact@example.com",
                "visa_status": "not_mentioned",
            },
        ],
    }

    valid_items = parse_and_validate_vacancies(raw_payload)
    assert len(valid_items) == 2
    assert valid_items[0].title == "Good Job"
    assert valid_items[1].title == "Another Good Job"


def test_parse_and_validate_supports_jobs_alias():
    raw_payload = {
        "jobs": [
            {
                "title": "Job via Alias",
                "text": "Detailed description text for testing alias.",
                "submit_url": "https://example.com/alias",
            }
        ]
    }
    valid_items = parse_and_validate_vacancies(raw_payload)
    assert len(valid_items) == 1
    assert valid_items[0].title == "Job via Alias"


def test_sync_chatgpt_vacancies_to_db_dry_run(db_session):
    items = [
        ChatGPTJobItem(
            title="Senior Automation Lead",
            company="Factory Corp",
            text="Detailed job description for automation lead.",
            submit_url="https://example.com/automation-lead",
            visa_status=VisaStatus.provided,
        )
    ]

    added, skipped = sync_chatgpt_vacancies_to_db(db_session, items, dry_run=True)
    assert added == 1
    assert skipped == 0
    # In dry-run mode, no records are committed
    assert db_session.query(Vacancy).count() == 0


def test_sync_chatgpt_vacancies_to_db_and_deduplication(db_session):
    items = [
        ChatGPTJobItem(
            title="Senior Automation Lead",
            company="Factory Corp",
            text="Detailed job description for automation lead.",
            submit_url="https://example.com/lead-1",
            visa_status=VisaStatus.provided,
        ),
        ChatGPTJobItem(
            title="Senior Automation Lead",
            company="Factory Corp",
            text="Detailed job description for automation lead duplicate.",
            submit_url="https://example.com/lead-1",  # Same URL in batch
            visa_status=VisaStatus.provided,
        ),
        ChatGPTJobItem(
            title="PLC Programmer",
            company="Tech Corp",
            text="Detailed job description for PLC programmer.",
            submit_email="hr@techcorp.com",
            visa_status=VisaStatus.provided,
        ),
    ]

    added, skipped = sync_chatgpt_vacancies_to_db(db_session, items, dry_run=False)
    assert added == 2
    assert skipped == 1

    stored = db_session.query(Vacancy).all()
    assert len(stored) == 2
    assert stored[0].source == DataSource.other
    assert stored[0].status == VacancyStatus.created

    # Second sync with same items should skip all
    added_2, skipped_2 = sync_chatgpt_vacancies_to_db(db_session, items, dry_run=False)
    assert added_2 == 0
    assert skipped_2 == 3


def test_fetch_gdrive_json_data_missing_url_raises():
    with patch("ljpa_reworked.services.chatgpt_gdrive.CHATGPT_GDRIVE_URL", ""):
        with pytest.raises(ValueError, match="Google Drive URL is not configured"):
            fetch_gdrive_json_data(url="")


def test_fetch_gdrive_json_data_success():
    fake_json_str = '{"vacancies": [{"title": "DevOps", "text": "Kubernetes and CI/CD description.", "submit_url": "https://example.com/devops"}]}'

    with (
        patch("gdown.download", return_value="/tmp/test_download.json") as mock_gdown,
        patch("builtins.open", mock_open(read_data=fake_json_str)),
        patch("os.path.exists", return_value=True),
        patch("os.path.getsize", return_value=len(fake_json_str)),
        patch("os.remove") as mock_remove,
    ):
        data = fetch_gdrive_json_data(
            url="https://drive.google.com/file/d/12345/view?usp=sharing"
        )
        assert data == {
            "vacancies": [
                {
                    "title": "DevOps",
                    "text": "Kubernetes and CI/CD description.",
                    "submit_url": "https://example.com/devops",
                }
            ]
        }
        mock_gdown.assert_called_once()
        mock_remove.assert_called_once()


def test_chatgpt_gdrive_service_run(db_session):
    fake_data = {
        "vacancies": [
            {
                "title": "Embedded Engineer",
                "company": "Chipset Co",
                "text": "Full job description for embedded systems.",
                "submit_url": "https://chipset.com/apply/1",
                "visa_status": "provided",
            }
        ]
    }

    with patch(
        "ljpa_reworked.services.chatgpt_gdrive.fetch_gdrive_json_data",
        return_value=fake_data,
    ):
        service = ChatGPTGDriveService(
            url="https://drive.google.com/file/d/test", dry_run=False
        )
        added, skipped = service.run(db_session)
        assert added == 1
        assert skipped == 0
        assert db_session.query(Vacancy).count() == 1
