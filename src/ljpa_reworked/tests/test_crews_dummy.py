import pytest

from ljpa_reworked.crews.email_generation_crew.email_generation_crew import (
    EmailGenerationCrew,
)
from ljpa_reworked.crews.resume_evaluation_crew.resume_evaluation_crew import (
    ResumeEvaluationCrew,
)
from ljpa_reworked.crews.resume_generation_crew.resume_generation_crew import (
    ResumeGenerationCrew,
)
from ljpa_reworked.crews.vacancy_review_crew.vacancy_review_crew import (
    VacancyReviewCrew,
)
from ljpa_reworked.models.crewai_pydantic_models import (
    BasicEvaluationCrewAI,
    EmailCrewAI,
    ProcessedPost,
    ResumeCrewAI,
    VacancyCrewAI,
)


@pytest.fixture
def dummy_vacancy_post():
    return """
    We are looking for a Senior Python Developer to join our team in Almaty, Kazakhstan!
    
    Requirements:
    - 5+ years of experience with Python
    - Strong knowledge of FastAPI and PostgreSQL
    - Experience with Docker and CI/CD
    
    If you are interested, please send your CV to careers@techcorp.kz
    """

@pytest.fixture
def dummy_vacancy_data():
    return {
        "title": "Senior Python Developer",
        "text": "Requirements: 5+ years of experience with Python, FastAPI, PostgreSQL, Docker.",
        "credentials": "Send CV to careers@techcorp.kz",
        "linkedin_url": "https://www.linkedin.com/jobs/view/123456789"
    }

def test_vacancy_review_crew(dummy_vacancy_post):
    crew = VacancyReviewCrew().crew()
    result = crew.kickoff(inputs={"linkedin_post": dummy_vacancy_post})
    
    # The result should be a VacancyCrewAI because the post is a vacancy
    assert result is not None
    assert isinstance(result.pydantic, VacancyCrewAI)
    assert result.pydantic.title is not None
    assert "Python" in result.pydantic.title or "Developer" in result.pydantic.title

def test_resume_evaluation_crew(dummy_vacancy_data):
    # This crew uses CV_FILE_PATH from config by default
    crew = ResumeEvaluationCrew().crew()
    result = crew.kickoff(inputs=dummy_vacancy_data)
    
    assert result is not None
    assert isinstance(result.pydantic, BasicEvaluationCrewAI)
    assert 0 <= result.pydantic.rating <= 100
    assert result.pydantic.summary is not None

def test_resume_generation_crew(dummy_vacancy_data):
    # Needs rating and summary from evaluation
    inputs = dummy_vacancy_data.copy()
    inputs.update({
        "rating": 85,
        "summary": "Strong match for the backend requirements with significant Python experience."
    })
    
    crew = ResumeGenerationCrew().crew()
    result = crew.kickoff(inputs=inputs)
    
    assert result is not None
    assert isinstance(result.pydantic, ResumeCrewAI)
    assert result.pydantic.personal_info.name is not None
    assert len(result.pydantic.experience) > 0

def test_email_generation_crew(dummy_vacancy_data):
    inputs = dummy_vacancy_data.copy()
    inputs["email_signature"] = "Best regards,\nIvan Ivanov\nSoftware Engineer"
    
    crew = EmailGenerationCrew().crew()
    result = crew.kickoff(inputs=inputs)
    
    assert result is not None
    assert isinstance(result.pydantic, EmailCrewAI)
    assert result.pydantic.subject is not None
    assert result.pydantic.body is not None
    assert "Best regards" in result.pydantic.body
