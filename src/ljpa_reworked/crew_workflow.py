import json
import os
import re
import urllib.request
from typing import TYPE_CHECKING

from ljpa_reworked.config import (
    EMAIL_SIGNATURE,
    LINKEDIN_PROFILE_URL,
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    PROFILE_FILE_PATH,
)
from ljpa_reworked.crews.email_generation_crew import EmailGenerationCrew
from ljpa_reworked.crews.resume_evaluation_crew import ResumeEvaluationCrew
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

SECTION_ALIAS_MAP = {
    "experience": "experience",
    "work experience": "experience",
    "professional experience": "experience",
    "employment": "experience",
    "education": "education",
    "academic background": "education",
    "skills": "skills",
    "technical skills": "skills",
    "key qualifications & expertise": "skills",
    "projects": "projects",
    "personal projects": "projects",
    "certifications": "certifications",
    "certificates": "certifications",
    "languages": "languages",
    "general information": "personal_info",
    "general info": "personal_info",
    "personal info": "personal_info",
    "summary": "summary",
    "executive summary": "summary",
}
CORE_PROFILE_SECTIONS = {"personal_info", "summary", "experience", "education", "skills"}


def read_profile_text(profile_path: str = PROFILE_FILE_PATH) -> str:
    """Read candidate profile text from local markdown file."""
    if not os.path.exists(profile_path):
        raise FileNotFoundError(f"Profile file not found at: {profile_path}")
    with open(profile_path, encoding="utf-8") as f:
        return f.read()


def parse_profile_sections(profile_text: str) -> list[str]:
    """Return canonical sections declared by level-two Markdown headings."""
    sections: list[str] = []
    for heading in re.findall(r"^##\s+(.+?)\s*$", profile_text, re.MULTILINE):
        canonical = SECTION_ALIAS_MAP.get(heading.casefold().strip())
        if canonical and canonical not in sections:
            sections.append(canonical)
    return sections


def validate_profile_completeness(profile_text: str) -> list[str]:
    """Reject a profile missing source sections needed for a truthful resume."""
    sections = parse_profile_sections(profile_text)
    missing = sorted(CORE_PROFILE_SECTIONS.difference(sections))
    if missing:
        raise ValueError(f"Missing required core sections: {', '.join(missing)}")
    return sections


def validate_resume_facts(
    resume: ResumeCrewAI,
    evaluation: BasicEvaluationCrewAI,
    *,
    present_sections: list[str] | None = None,
) -> None:
    """Validate generated resume against deterministic profile sections and fact rules."""
    if evaluation.missing_mandatory_facts:
        raise ValueError(
            f"Missing mandatory profile facts: {', '.join(evaluation.missing_mandatory_facts)}"
        )

    required_sections = present_sections or evaluation.required_profile_sections
    for section in required_sections:
        canonical = SECTION_ALIAS_MAP.get(section.casefold().strip(), section)
        if canonical not in SECTION_ALIAS_MAP.values():
            raise ValueError(f"Unknown required profile section: '{section}'")
        if canonical in {"personal_info", "summary", "languages"}:
            continue
        if not getattr(resume, canonical, None):
            raise ValueError(
                f"Required profile section '{section}' is missing or empty in generated resume."
            )

    for exp in resume.experience:
        if len(exp.description) < 3:
            raise ValueError(
                f"Experience entry '{exp.title}' at '{exp.company}' has fewer than 3 bullet points."
            )
    for proj in resume.projects:
        if len(proj.highlights) < 3:
            raise ValueError(
                f"Project entry '{proj.title}' has fewer than 3 bullet points."
            )


@crewai_retry_handler
def crewai_evaluate_vacancy(vacancy: "Vacancy") -> BasicEvaluationCrewAI:
    profile_text = read_profile_text(PROFILE_FILE_PATH)
    present_sections = validate_profile_completeness(profile_text)
    crew = ResumeEvaluationCrew().crew()
    inputs = {
        "text": vacancy.text,
        "title": vacancy.title,
        "submit_email": vacancy.submit_email or "",
        "submit_url": vacancy.submit_url or "",
        "linkedin_url": LINKEDIN_PROFILE_URL,
        "candidate_profile": profile_text,
        "required_profile_sections": present_sections,
    }
    crew_output = crew.kickoff(inputs=inputs)
    rate_limitter.record(crew.usage_metrics.successful_requests)
    return crew_output.tasks_output[0].pydantic


def crewai_generate_resume(
    vacancy: "Vacancy", evaluation: BasicEvaluationCrewAI
) -> ResumeCrewAI:
    """Generate tailored resume via a narrow direct gateway adapter with bounded timeout."""
    profile_text = read_profile_text(PROFILE_FILE_PATH)
    present_sections = validate_profile_completeness(profile_text)

    url = f"{LLM_BASE_URL.rstrip('/')}/chat/completions"
    system_prompt = (
        "You are an expert resume generator. Create a tailored candidate resume JSON matching the ResumeCrewAI schema. "
        "Strict rules:\n"
        "1. Extract ONLY facts from the provided profile. MUST NOT invent any jobs, employers, dates, qualifications, skills, certifications, achievements, or contact data not present in the candidate profile.\n"
        "2. Each included experience role and project MUST have at least 3 detailed, factual bullet points in description/highlights.\n"
        "3. Output ONLY valid JSON matching the specified Pydantic schema. No markdown code blocks, no extra commentary.\n"
        "4. Be high-density, concise, and direct. Keep bullet points punchy (10-20 words each, 3-4 bullets per entry) for maximum impact and fast generation."
    )
    json_schema = ResumeCrewAI.model_json_schema()
    user_prompt = (
        f"Vacancy Title: {vacancy.title}\n"
        f"Vacancy Details: {vacancy.text}\n"
        f"LinkedIn URL: {LINKEDIN_PROFILE_URL}\n"
        f"Evaluation Summary: {evaluation.summary}\n"
        f"Evaluation Rating: {evaluation.rating}\n"
        f"Required Profile Sections: {present_sections}\n"
        f"Prioritized Facts: {evaluation.prioritized_facts}\n"
        f"Missing Facts: {evaluation.missing_mandatory_facts}\n\n"
        f"Candidate Profile Markdown:\n{profile_text}\n\n"
        f"Output JSON strictly matching this schema:\n{json.dumps(json_schema)}"
    )

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 4096,
        "stream": False,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LLM_API_KEY}",
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=90.0) as resp:
        res_data = json.loads(resp.read().decode("utf-8"))
        raw_content = res_data["choices"][0]["message"]["content"].strip()
        if raw_content.startswith("```json"):
            raw_content = raw_content[7:]
        if raw_content.startswith("```"):
            raw_content = raw_content[3:]
        if raw_content.endswith("```"):
            raw_content = raw_content[:-3]
        resume = ResumeCrewAI.model_validate_json(raw_content.strip())

    rate_limitter.record(1)
    validate_resume_facts(resume, evaluation, present_sections=present_sections)
    return resume



@crewai_retry_handler
def crewai_generate_email(vacancy: "Vacancy") -> EmailCrewAI:
    crew = EmailGenerationCrew().crew()
    inputs = {}
    inputs["text"] = vacancy["text"] if isinstance(vacancy, dict) else vacancy.text
    inputs["title"] = vacancy["title"] if isinstance(vacancy, dict) else vacancy.title
    inputs["submit_email"] = (
        vacancy.get("submit_email") or ""
        if isinstance(vacancy, dict)
        else (vacancy.submit_email or "")
    )
    inputs["submit_url"] = (
        vacancy.get("submit_url") or ""
        if isinstance(vacancy, dict)
        else (vacancy.submit_url or "")
    )
    inputs["email_signature"] = EMAIL_SIGNATURE
    crew_output = crew.kickoff(inputs=inputs)
    rate_limitter.record(crew.usage_metrics.successful_requests)
    return crew_output.tasks_output[0].pydantic
