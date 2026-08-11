from unittest.mock import MagicMock, patch

import pytest

from ljpa_reworked.crew_workflow import (
    crewai_evaluate_vacancy,
    crewai_generate_resume,
    read_profile_text,
)
from ljpa_reworked.crews.resume_evaluation_crew.resume_evaluation_crew import (
    ResumeEvaluationCrew,
)
from ljpa_reworked.crews.resume_generation_crew.resume_generation_crew import (
    ResumeGenerationCrew,
)
from ljpa_reworked.models.crewai_pydantic_models import (
    BasicEvaluationCrewAI,
    EducationCrewAI,
    ExperienceCrewAI,
    PersonalInfoCrewAI,
    ResumeCrewAI,
    SkillCrewAI,
)


def test_read_profile_text_success_and_failure(tmp_path):
    """Verify read_profile_text reads valid UTF-8 file and raises clear error when missing."""
    test_file = tmp_path / "test_profile.md"
    content = '## General Information\nName: Test\n## Summary\nEngineer\n## Experience\n- Role\n## Education\n- Degree\n## Skills\n- Python'
    test_file.write_text(content, encoding="utf-8")

    assert read_profile_text(str(test_file)) == content

    missing_file = tmp_path / "missing_profile.md"
    with pytest.raises(FileNotFoundError, match="Profile file not found"):
        read_profile_text(str(missing_file))


def test_resume_evaluation_crew_no_knowledge_or_embedder():
    """Verify ResumeEvaluationCrew does not construct Knowledge or embedder."""
    with patch("ljpa_reworked.crews.resume_evaluation_crew.resume_evaluation_crew.create_llm", return_value=MagicMock()):
        crew_obj = ResumeEvaluationCrew()
        assert not hasattr(crew_obj, "profile_md")
        assert not hasattr(crew_obj, "embedder") or crew_obj.embedder is None
        c = crew_obj.crew()
        assert getattr(c, "knowledge", None) is None


def test_resume_generation_crew_no_knowledge_or_embedder():
    """Verify ResumeGenerationCrew does not construct Knowledge or embedder."""
    with patch("ljpa_reworked.crews.resume_generation_crew.resume_generation_crew.create_llm", return_value=MagicMock()):
        crew_obj = ResumeGenerationCrew()
        assert not hasattr(crew_obj, "profile_md")
        assert not hasattr(crew_obj, "embedder") or crew_obj.embedder is None
        c = crew_obj.crew()
        assert getattr(c, "knowledge", None) is None


def test_crewai_evaluate_vacancy_passes_candidate_profile(tmp_path):
    """Verify crewai_evaluate_vacancy passes full profile text in inputs['candidate_profile']."""
    synthetic_profile = '## General Information\nName: Test\n## Summary\nEngineer\n## Experience\n- Role\n## Education\n- Degree\n## Skills\n- Python'
    test_profile_path = tmp_path / "profile.md"
    test_profile_path.write_text(synthetic_profile, encoding="utf-8")

    mock_vacancy = MagicMock()
    mock_vacancy.text = "Python Backend Vacancy"
    mock_vacancy.title = "Python Engineer"
    mock_vacancy.submit_email = "jobs@example.com"
    mock_vacancy.submit_url = "https://example.com/job"

    mock_crew = MagicMock()
    mock_crew.usage_metrics.successful_requests = 1
    mock_crew_output = MagicMock()
    mock_eval = BasicEvaluationCrewAI(summary="Good candidate", rating=85)
    mock_task_output = MagicMock()
    mock_task_output.pydantic = mock_eval
    mock_crew_output.tasks_output = [mock_task_output]
    mock_crew.kickoff.return_value = mock_crew_output

    with patch("ljpa_reworked.crew_workflow.PROFILE_FILE_PATH", str(test_profile_path)), \
         patch("ljpa_reworked.crew_workflow.ResumeEvaluationCrew") as mock_crew_cls:
        mock_crew_cls.return_value.crew.return_value = mock_crew

        res = crewai_evaluate_vacancy(mock_vacancy)

        assert res == mock_eval
        mock_crew.kickoff.assert_called_once()
        call_kwargs = mock_crew.kickoff.call_args[1]
        inputs = call_kwargs["inputs"]
        assert "candidate_profile" in inputs
        assert inputs["candidate_profile"] == synthetic_profile


def test_crewai_generate_resume_passes_candidate_profile(tmp_path):
    """Verify crewai_generate_resume passes full profile text in inputs['candidate_profile']."""
    synthetic_profile = '## General Information\nName: Test\n## Summary\nEngineer\n## Experience\n- Role\n## Education\n- Degree\n## Skills\n- Python'
    test_profile_path = tmp_path / "profile.md"
    test_profile_path.write_text(synthetic_profile, encoding="utf-8")

    mock_vacancy = MagicMock()
    mock_vacancy.text = "Python Engineer"
    mock_vacancy.title = "Backend Dev"
    mock_vacancy.submit_email = "jobs@example.com"
    mock_vacancy.submit_url = "https://example.com/job"

    mock_eval = BasicEvaluationCrewAI(summary="Good fit", rating=90)

    mock_resume = ResumeCrewAI(
        personal_info=PersonalInfoCrewAI(
            name="Test Candidate",
            email="test@example.com",
            phone="+1 555 0199",
            address="123 Main St",
            location="Berlin, Germany",
        ),
        summary="A software engineer",
        education=[EducationCrewAI(course="Degree", institution="University", location="Berlin", start_date="2016", end_date="2020")],
        experience=[ExperienceCrewAI(title="Engineer", company="Company", location="Berlin", start_date="2020", end_date="Present", description=["One", "Two", "Three"])],
        skills=[SkillCrewAI(title="Languages", elements=["Python"])],
        projects=[],
        certifications=[],
    )

    import json

    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "choices": [{"message": {"content": mock_resume.model_dump_json()}}]
    }).encode("utf-8")
    mock_response.__enter__.return_value = mock_response

    captured_requests = []

    def mock_urlopen(req, timeout=None):
        captured_requests.append((req, timeout))
        return mock_response

    with patch("ljpa_reworked.crew_workflow.PROFILE_FILE_PATH", str(test_profile_path)), \
         patch("urllib.request.urlopen", side_effect=mock_urlopen):

        res = crewai_generate_resume(mock_vacancy, mock_eval)

        assert res.personal_info.name == mock_resume.personal_info.name
        assert len(captured_requests) == 1
        req, timeout = captured_requests[0]
        payload = json.loads(req.data.decode("utf-8"))
        user_msg = payload["messages"][1]["content"]
        assert synthetic_profile in user_msg
