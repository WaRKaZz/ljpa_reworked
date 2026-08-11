from unittest.mock import MagicMock, patch

from ljpa_reworked.crews.resume_generation_crew.resume_generation_crew import (
    ResumeGenerationCrew,
)
from ljpa_reworked.models.crewai_pydantic_models import (
    PersonalInfoCrewAI,
    ResumeCrewAI,
    SkillCrewAI,
)


def test_resume_generation_crew_hermetic_probe():
    """Hermetic synthetic probe verifying ResumeGenerationCrew inputs without network or LLM execution."""
    synthetic_inputs = {
        "title": "Senior Python Backend Engineer",
        "text": (
            "We are looking for a Senior Python Backend Engineer to build scalable microservices using Python, "
            "FastAPI, and PostgreSQL. Requirements: 5+ years experience with Python, async programming, Docker, and CI/CD."
        ),
        "submit_email": "jobs@example.com",
        "submit_url": "https://example.com/careers/python-engineer",
        "linkedin_url": "https://linkedin.com/in/testcandidate",
        "rating": 85,
        "summary": "Strong candidate with extensive Python and backend architecture experience.",
        "candidate_profile": (
            "# Candidate Profile\n\n## Personal Info\n- Name: Test Candidate\n- Email: candidate@example.com\n"
            "- Phone: +1 555-0100\n- Location: New York, USA\n\n## Summary\n"
            "Experienced Python Backend Engineer with 6 years experience in microservices.\n\n"
            "## Experience\n- Role: Senior Python Developer at Tech Corp (2020-Present)\n"
            "  Highlights: Built FastAPI microservices, optimized PostgreSQL queries.\n\n"
            "## Education\n- BS Computer Science, Tech University (2016-2020)\n\n"
            "## Skills\n- Python, FastAPI, PostgreSQL, Docker, CI/CD"
        ),
    }

    mock_llm = MagicMock()
    mock_crew = MagicMock()
    mock_crew_output = MagicMock()
    mock_task_output = MagicMock()

    mock_resume = ResumeCrewAI(
        personal_info=PersonalInfoCrewAI(
            name="Test Candidate",
            email="candidate@example.com",
            phone="+1 555-0100",
            address="123 Test St",
            location="New York, USA",
        ),
        summary="Experienced Python Backend Engineer",
        education=[],
        experience=[],
        skills=[SkillCrewAI(title="Languages", elements=["Python", "FastAPI"])],
        projects=[],
        certifications=[],
    )
    mock_task_output.pydantic = mock_resume
    mock_crew_output.tasks_output = [mock_task_output]
    mock_crew.kickoff.return_value = mock_crew_output

    with (
        patch(
            "ljpa_reworked.crews.resume_generation_crew.resume_generation_crew.create_llm",
            return_value=mock_llm,
        ),
        patch("crewai.Crew.kickoff", return_value=mock_crew_output) as mock_kickoff,
    ):
        crew_instance = ResumeGenerationCrew()
        c = crew_instance.crew()

        assert getattr(crew_instance, "profile_md", None) is None
        assert getattr(crew_instance, "embedder", None) is None
        assert getattr(c, "knowledge", None) is None

        crew_result = c.kickoff(inputs=synthetic_inputs)
        mock_kickoff.assert_called_once_with(inputs=synthetic_inputs)

        assert "candidate_profile" in synthetic_inputs
        resume = crew_result.tasks_output[0].pydantic
        assert isinstance(resume, ResumeCrewAI)
        assert resume.personal_info.name == "Test Candidate"
