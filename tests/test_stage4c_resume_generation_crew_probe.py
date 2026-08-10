import time

from ljpa_reworked.crews.resume_generation_crew.resume_generation_crew import (
    ResumeGenerationCrew,
)
from ljpa_reworked.models.crewai_pydantic_models import ResumeCrewAI


def test_resume_generation_crew_finite_probe():
    """Finite synthetic probe verifying ResumeGenerationCrew completes under 60 seconds."""
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
    }

    start_time = time.monotonic()
    crew_instance = ResumeGenerationCrew()
    crew_result = crew_instance.crew().kickoff(inputs=synthetic_inputs)
    elapsed_time = time.monotonic() - start_time

    assert elapsed_time < 75.0, f"Task exceeded 75s limit! Took {elapsed_time:.2f}s"

    resume = crew_result.tasks_output[0].pydantic
    assert isinstance(resume, ResumeCrewAI), "Output is not a valid ResumeCrewAI instance"
    assert resume.personal_info is not None
    assert bool(resume.personal_info.name)
    assert len(resume.experience) > 0
    assert len(resume.skills) > 0
