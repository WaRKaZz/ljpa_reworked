import json
import os
import re
from typing import TYPE_CHECKING

from ljpa_reworked.config import (
    EMAIL_SIGNATURE,
    LINKEDIN_PROFILE_URL,
    PROFILE_FILE_PATH,
)
from ljpa_reworked.crews.email_generation_crew import EmailGenerationCrew
from ljpa_reworked.crews.resume_evaluation_crew import ResumeEvaluationCrew
from ljpa_reworked.crews.resume_generation_crew import ResumeGenerationCrew
from ljpa_reworked.decorators import crewai_retry_handler
from ljpa_reworked.models.crewai_pydantic_models import (
    BasicEvaluationCrewAI,
    EmailCrewAI,  # noqa
    ResumeCrewAI,
)
from ljpa_reworked.resume_static_profile import (
    merge_static_resume_profile,
    parse_static_resume_profile,
)
from ljpa_reworked.services.dynamic_rate_limiter import DynamicRateLimiter
from ljpa_reworked.services.rendercv_helper import render_resume_crewai_to_pdf

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
    rate_limitter.acquire()
    crew_output = crew.kickoff(inputs=inputs)
    rate_limitter.record(getattr(crew_output.token_usage, "successful_requests", 0))
    if crew_output.pydantic is None:
        raise ValueError("CrewAI evaluation returned no structured output.")
    # The profile passed the deterministic completeness check above. A vacancy
    # requirement the candidate does not meet affects rating, never profile completeness.
    return crew_output.pydantic.model_copy(update={"missing_mandatory_facts": []})


def crewai_generate_resume(
    vacancy: "Vacancy",
    evaluation: BasicEvaluationCrewAI,
    *,
    layout_feedback: str = "",
    prior_resume_json: str = "",
) -> ResumeCrewAI:
    """Generate through CrewAI so Task guardrails retry invalid structured output."""
    profile_text = read_profile_text(PROFILE_FILE_PATH)
    present_sections = validate_profile_completeness(profile_text)
    static_profile = parse_static_resume_profile(profile_text)
    crew = ResumeGenerationCrew().crew()
    rate_limitter.acquire()
    crew_output = crew.kickoff(
        inputs={
            "title": vacancy.title,
            "text": vacancy.text,
            "linkedin_url": LINKEDIN_PROFILE_URL or "",
            "candidate_profile": profile_text,
            "summary": evaluation.summary,
            "rating": evaluation.rating,
            "required_profile_sections": present_sections,
            "prioritized_facts": evaluation.prioritized_facts,
            "missing_mandatory_facts": evaluation.missing_mandatory_facts,
            "retry_feedback": layout_feedback,
            "prior_resume_json": prior_resume_json,
        }
    )
    rate_limitter.record(getattr(crew_output.token_usage, "successful_requests", 0))
    dynamic_resume = json.loads(crew_output.raw)
    resume = ResumeCrewAI.model_validate(
        merge_static_resume_profile(dynamic_resume, static_profile)
    )
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
    rate_limitter.acquire()
    crew_output = crew.kickoff(inputs=inputs)
    rate_limitter.record(getattr(crew_output.token_usage, "successful_requests", 0))
    if crew_output.pydantic is None:
        raise ValueError("CrewAI email returned no structured output.")
    return crew_output.pydantic


def _format_numeric_layout_feedback(raw_error: str) -> str:
    """Extract numeric deficit/excess from validation error and formulate explicit correction instructions."""
    project_bullet_match = re.search(
        r"Project entry '(.+)' has fewer than 3 bullet points\.", raw_error
    )
    if project_bullet_match:
        title = project_bullet_match.group(1)
        return (
            f"{raw_error}\n"
            f"PROJECT BULLET CORRECTION REQUIRED: Project '{title}' must contain exactly 3 or 4 highlights. "
            f"Add truthful technical scope, implementation work, and outcome details from the candidate profile. "
            f"Do not remove the project or invent facts. Return the complete replacement JSON."
        )

    common_instructions = (
        "\nRenderCV entry policy: RenderCV has allow_page_break_in_entries set to false, so whole section entries move together to the next page when overflow occurs instead of splitting.\n"
        "ALLOWED FIELDS IN PRIORITY ORDER:\n"
        "1. Summary section (expand/trim up to max 500 characters limit).\n"
        "2. Skill elements (add or trim technical skill elements in existing categories).\n"
        "3. Existing experience descriptions and project highlights (expand or trim bullet points with technical detail).\n"
        "FORBIDDEN CHANGES: Do NOT invent fake roles, companies, projects, certifications, or dates. Do not add fabricated history.\n"
        "PRESERVED CONSTRAINTS: Preserve all verified candidate profile facts, maintain section order (Summary, Skills, Experience, Education, Certifications, Projects), and adhere strictly to the ResumeCrewAI Pydantic schema.\n"
        "FINAL JSON REMINDER: Return strictly one raw valid JSON object matching ResumeCrewAI schema without markdown syntax or comments."
    )

    match = re.search(
        r"Page (\d+) \(non-final\) character count \((\d+)\) is less than minimum 3000 characters",
        raw_error,
    )
    if match:
        page_num = match.group(1)
        count = int(match.group(2))
        add_target = 3100 - count
        return (
            f"{raw_error}\n"
            f"NUMERIC CORRECTION REQUIRED: Page {page_num} has {count} characters (SHORT of 3000 minimum). "
            f"You MUST expand the resume text by approximately {add_target} characters to land near 3100 characters. "
            f"Add truthful technical detail to existing experience descriptions, project highlights, or skill elements. "
            f"{common_instructions}"
        )

    match_final = re.search(
        r"Page (\d+) \(final\) character count \((\d+)\) is less than minimum 1400 characters",
        raw_error,
    )
    if match_final:
        page_num = match_final.group(1)
        count = int(match_final.group(2))
        target_mid = 1500
        add_target = target_mid - count
        return (
            f"{raw_error}\n"
            f"NUMERIC CORRECTION REQUIRED: Final Page {page_num} has {count} characters (SHORT of 1400 min requirement). "
            f"You MUST add approximately {add_target} characters across experience/project sections to land near {target_mid} characters."
            f"{common_instructions}"
        )

    return raw_error


def crewai_generate_resume_with_retry(
    vacancy: "Vacancy",
    evaluation: BasicEvaluationCrewAI,
    *,
    max_retries: int = 3,
) -> tuple[ResumeCrewAI, str]:
    """Generate a resume and render to PDF, making at most max_retries retry with factual layout feedback if page budget fails."""
    import tempfile

    attempts = 0
    max_attempts = max_retries + 1
    layout_feedback = ""
    prior_resume_json = ""
    last_error: Exception | None = None
    last_parsed_resume: ResumeCrewAI | None = None

    while attempts < max_attempts:
        attempts += 1
        with tempfile.NamedTemporaryFile(
            prefix=f"rendercv_attempt{attempts}_", suffix=".pdf", delete=False
        ) as tmp:
            temp_pdf_path = tmp.name

        try:
            resume = crewai_generate_resume(
                vacancy=vacancy,
                evaluation=evaluation,
                layout_feedback=layout_feedback,
                prior_resume_json=prior_resume_json,
            )
            last_parsed_resume = resume
            render_resume_crewai_to_pdf(resume, temp_pdf_path)
            return resume, temp_pdf_path
        except Exception as err:
            if not str(err).startswith("RenderCV output failed page layout validation:"):
                if os.path.exists(temp_pdf_path):
                    os.remove(temp_pdf_path)
                raise
            last_error = err
            if os.path.exists(temp_pdf_path):
                try:
                    os.remove(temp_pdf_path)
                except OSError:
                    pass

            if attempts < max_attempts:
                layout_feedback = _format_numeric_layout_feedback(str(err))
                if last_parsed_resume is not None:
                    prior_resume_json = json.dumps(
                        last_parsed_resume.model_dump(mode="json"), ensure_ascii=False
                    )
            else:
                raise last_error from err
