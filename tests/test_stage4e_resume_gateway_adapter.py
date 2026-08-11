import json
from unittest.mock import MagicMock, patch

import pytest

from ljpa_reworked.crew_workflow import crewai_generate_resume
from ljpa_reworked.models.crewai_pydantic_models import (
    BasicEvaluationCrewAI,
    EducationCrewAI,
    ExperienceCrewAI,
    PersonalInfoCrewAI,
    ResumeCrewAI,
    SkillCrewAI,
)


def test_crewai_generate_resume_gateway_adapter_payload_and_success(tmp_path):
    """Verify crewai_generate_resume uses direct gateway adapter with max_tokens=4096, stream=False, and bounded timeout."""
    synthetic_profile = (
        "## Personal Info\n- Name: Test User\n- Email: test@example.com\n- Phone: +1 555-0100\n- Location: NY\n"
        "## Summary\nBackend Engineer\n"
        "## Experience\n- Role: Dev at Corp (2020-Present)\n  Highlights: High throughput APIs, DB tuning, CI/CD.\n"
        "## Education\n- BS CS, University (2016-2020)\n"
        "## Skills\n- Python, FastAPI, SQL"
    )
    test_profile_path = tmp_path / "profile.md"
    test_profile_path.write_text(synthetic_profile, encoding="utf-8")

    mock_vacancy = MagicMock()
    mock_vacancy.text = "Python Backend Vacancy"
    mock_vacancy.title = "Backend Engineer"
    mock_vacancy.submit_email = "jobs@example.com"
    mock_vacancy.submit_url = "https://example.com/job"

    mock_eval = BasicEvaluationCrewAI(
        summary="Qualified candidate",
        rating=90,
        required_profile_sections=["personal_info", "summary", "experience", "education", "skills"],
        prioritized_facts=["High throughput APIs"],
        missing_mandatory_facts=[],
    )

    valid_resume = ResumeCrewAI(
        personal_info=PersonalInfoCrewAI(
            name="Test User",
            email="test@example.com",
            phone="+1 555-0100",
            address="123 Main St",
            location="NY",
        ),
        summary="Backend Engineer",
        education=[EducationCrewAI(course="BS CS", institution="University", location="NY", start_date="2016", end_date="2020")],
        experience=[ExperienceCrewAI(title="Dev", company="Corp", location="NY", start_date="2020", end_date="Present", description=["High throughput APIs", "DB tuning", "CI/CD"])],
        skills=[SkillCrewAI(title="Languages", elements=["Python"])],
        projects=[],
        certifications=[],
    )

    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "choices": [{"message": {"content": valid_resume.model_dump_json()}}]
    }).encode("utf-8")
    mock_response.__enter__.return_value = mock_response

    captured_requests = []

    def mock_urlopen(req, timeout=None):
        captured_requests.append((req, timeout))
        return mock_response

    with patch("ljpa_reworked.crew_workflow.PROFILE_FILE_PATH", str(test_profile_path)), \
         patch("urllib.request.urlopen", side_effect=mock_urlopen):

        res = crewai_generate_resume(mock_vacancy, mock_eval)

        assert isinstance(res, ResumeCrewAI)
        assert res.personal_info.name == "Test User"
        assert len(captured_requests) == 1

        req, timeout = captured_requests[0]
        assert timeout == 90.0
        payload = json.loads(req.data.decode("utf-8"))
        assert payload["max_tokens"] == 4096
        assert payload["stream"] is False
        assert len(payload["messages"]) >= 2
        assert "messages" in payload


def test_crewai_generate_resume_raises_immediately_on_timeout(tmp_path):
    """Verify crewai_generate_resume fails fast on timeout without retry loops."""
    synthetic_profile = (
        "## Personal Info\n- Name: Test User\n- Email: test@example.com\n- Phone: +1 555-0100\n- Location: NY\n"
        "## Summary\nBackend Engineer\n"
        "## Experience\n- Role: Dev at Corp (2020-Present)\n  Highlights: High throughput APIs, DB tuning, CI/CD.\n"
        "## Education\n- BS CS, University (2016-2020)\n"
        "## Skills\n- Python, FastAPI, SQL"
    )
    test_profile_path = tmp_path / "profile.md"
    test_profile_path.write_text(synthetic_profile, encoding="utf-8")

    mock_vacancy = MagicMock()
    mock_vacancy.text = "Python Backend Vacancy"
    mock_vacancy.title = "Backend Engineer"
    mock_vacancy.submit_email = "jobs@example.com"
    mock_vacancy.submit_url = "https://example.com/job"

    mock_eval = BasicEvaluationCrewAI(summary="Qualified candidate", rating=90)

    call_count = 0

    def mock_urlopen_timeout(req, timeout=None):
        nonlocal call_count
        call_count += 1
        raise TimeoutError("Request timed out")

    with patch("ljpa_reworked.crew_workflow.PROFILE_FILE_PATH", str(test_profile_path)), \
         patch("urllib.request.urlopen", side_effect=mock_urlopen_timeout):

        with pytest.raises((TimeoutError, Exception), match="timed out|Request timed out"):
            crewai_generate_resume(mock_vacancy, mock_eval)

        # Fails immediately without retry loop
        assert call_count == 1
