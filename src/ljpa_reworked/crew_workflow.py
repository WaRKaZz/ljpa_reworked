from typing import TYPE_CHECKING

from ljpa_reworked.config import EMAIL_SIGNATURE, LINKEDIN_PROFILE_URL
from ljpa_reworked.crews.email_generation_crew import EmailGenerationCrew
from ljpa_reworked.crews.resume_evaluation_crew import ResumeEvaluationCrew
from ljpa_reworked.crews.resume_generation_crew import ResumeGenerationCrew
from ljpa_reworked.decorators import crewai_retry_handler
from ljpa_reworked.models.crewai_pydantic_models import (
    BasicEvaluationCrewAI,
    EmailCrewAI,  # noqa
    ResumeCrewAI,
)
from ljpa_reworked.services.dynamic_rate_limiter import DynamicRateLimiter

if TYPE_CHECKING:
    from ljpa_reworked.models.database_models import Vacancy

rate_limitter = DynamicRateLimiter()


@crewai_retry_handler
def crewai_evaluate_vacancy(vacancy: "Vacancy") -> BasicEvaluationCrewAI:
    crew = ResumeEvaluationCrew().crew()
    inputs = {}
    inputs["text"] = vacancy.text
    inputs["title"] = vacancy.title
    inputs["submit_email"] = vacancy.submit_email or ""
    inputs["submit_url"] = vacancy.submit_url or ""
    inputs["linkedin_url"] = LINKEDIN_PROFILE_URL
    crew_output = crew.kickoff(inputs=inputs)
    rate_limitter.record(crew.usage_metrics.successful_requests)
    evaluation: BasicEvaluationCrewAI = crew_output.tasks_output[0].pydantic
    return evaluation


@crewai_retry_handler
def crewai_generate_resume(
    vacancy: "Vacancy", evaluation: BasicEvaluationCrewAI
) -> ResumeCrewAI:
    crew = ResumeGenerationCrew().crew()
    inputs = {}
    inputs["text"] = vacancy.text
    inputs["title"] = vacancy.title
    inputs["submit_email"] = vacancy.submit_email or ""
    inputs["submit_url"] = vacancy.submit_url or ""
    inputs["linkedin_url"] = LINKEDIN_PROFILE_URL
    inputs["rating"] = evaluation.rating
    inputs["summary"] = evaluation.summary
    crew_output = crew.kickoff(inputs=inputs)
    rate_limitter.record(crew.usage_metrics.successful_requests)
    resume: ResumeCrewAI = crew_output.tasks_output[0].pydantic
    return resume


@crewai_retry_handler
def crewai_generate_email(vacancy: "Vacancy") -> EmailCrewAI:
    crew = EmailGenerationCrew().crew()
    inputs = {}
    inputs["text"] = vacancy["text"] if isinstance(vacancy, dict) else vacancy.text
    inputs["title"] = vacancy["title"] if isinstance(vacancy, dict) else vacancy.title
    inputs["submit_email"] = (
        vacancy.get("submit_email") or vacancy.get("credentials") or ""
        if isinstance(vacancy, dict)
        else (vacancy.submit_email or "")
    )
    inputs["submit_url"] = (
        vacancy.get("submit_url") or vacancy.get("url") or ""
        if isinstance(vacancy, dict)
        else (vacancy.submit_url or "")
    )
    inputs["email_signature"] = EMAIL_SIGNATURE
    crew_output = crew.kickoff(inputs=inputs)
    rate_limitter.record(crew.usage_metrics.successful_requests)
    email: EmailCrewAI = crew_output.tasks_output[0].pydantic
    return email
