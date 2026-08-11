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
    crew_output = crew.kickoff(inputs=inputs)
    rate_limitter.record(crew.usage_metrics.successful_requests)
    return crew_output.tasks_output[0].pydantic


def crewai_generate_resume(
    vacancy: "Vacancy",
    evaluation: BasicEvaluationCrewAI,
    *,
    layout_feedback: str = "",
) -> ResumeCrewAI:
    """Generate a JSON resume through the gateway, optionally correcting a prior layout miss."""
    profile_text = read_profile_text(PROFILE_FILE_PATH)
    present_sections = validate_profile_completeness(profile_text)

    url = f"{LLM_BASE_URL.rstrip('/')}/chat/completions"
    system_prompt = (
        "Return one raw valid JSON object for ResumeCrewAI. No markdown, explanation, or extra keys. "
        "Output fields: personal_info(name,email,phone,address,location,linkedin_url,target_title); "
        "summary; education(course,institution,location,start_date,end_date); "
        "experience(title,company,location,start_date,end_date,description); "
        "skills(title,elements); projects(title,description,start_date,end_date,highlights); "
        "certifications(title,issuer,date,url).\n"
        "SCHEMA LIMITS: summary <= 500 visible characters. skills is an array of objects; each object has title as a string and elements as a JSON array: [\"TIA Portal\", \"WinCC\"]. Never use a comma-separated string for elements.\n"
        "Write sections in this order: Summary, Skills, Experience, Education, Certifications, Projects. "
        "Create 3 skill categories with 4-5 elements per category. Every experience has 3 concise, highly relevant bullets. "
        "Every project has 2-3 detailed highlights.\n"
        "PAGE REQUIREMENT: RenderCV does not split an entry. Target overall length ~3350-3400 characters. "
        "If a resume spans multiple pages, each non-final page must contain 3300-3475 visible characters; "
        "the final page must contain at least 1400. If 1 page, it must contain 1400-3475 characters.\n"
        "Use candidate, vacancy, and general industrial-automation knowledge freely. Add ATS keywords, credible technical "
        "responsibilities, implementation details, and outcomes."
    )
    feedback_block = ""
    if layout_feedback:
        feedback_block = (
            f"!!! CRITICAL LAYOUT RETRY CORRECTION REQUIRED !!!\n"
            f"{layout_feedback}\n"
            f"MUST satisfy the numeric character addition/trimming requirement specified above.\n"
            f"==================================================\n\n"
        )

    user_prompt = (
        f"{feedback_block}"
        f"Vacancy title: {vacancy.title}\n"
        f"Vacancy: {vacancy.text}\n"
        f"Priorities: {evaluation.prioritized_facts}\n"
        f"Required sections: {present_sections}\n"
        f"Candidate profile:\n{profile_text}"
    )
    if layout_feedback:
        user_prompt += f"\n\nFINAL REMINDER: {layout_feedback}"

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

    with urllib.request.urlopen(req, timeout=120.0) as resp:
        res_data = json.loads(resp.read().decode("utf-8"))
        raw_content = res_data["choices"][0]["message"]["content"].strip()
        if raw_content.startswith("```json"):
            raw_content = raw_content[7:]
        if raw_content.startswith("```"):
            raw_content = raw_content[3:]
        if raw_content.endswith("```"):
            raw_content = raw_content[:-3]
        payload_json = json.loads(raw_content.strip())
        # ponytail: tolerate common JSON-shape slips from the gateway; schema remains strict after normalization.
        if isinstance(payload_json.get("summary"), str):
            payload_json["summary"] = payload_json["summary"][:500]
        for skill in payload_json.get("skills", []):
            if isinstance(skill.get("elements"), str):
                skill["elements"] = [
                    item.strip() for item in skill["elements"].split(",") if item.strip()
                ]
        for entry in payload_json.get("experience", []):
            if isinstance(entry.get("description"), str):
                entry["description"] = [
                    item.strip(" •-\t")
                    for item in re.split(r"(?:\r?\n|(?<=[.!?])\s+)", entry["description"])
                    if item.strip(" •-\t")
                ]
        for entry in payload_json.get("projects", []):
            if isinstance(entry.get("description"), list):
                entry["description"] = " ".join(entry["description"])
            if isinstance(entry.get("highlights"), str):
                entry["highlights"] = [
                    item.strip(" •-\t")
                    for item in re.split(r"(?:\r?\n|(?<=[.!?])\s+)", entry["highlights"])
                    if item.strip(" •-\t")
                ]
        resume = ResumeCrewAI.model_validate(payload_json)

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


def _format_numeric_layout_feedback(raw_error: str) -> str:
    """Extract numeric deficit/excess from validation error and formulate explicit correction instructions."""
    match = re.search(
        r"Page (\d+) \(non-final\) character count \((\d+)\) is outside required range \[3300, 3475\]",
        raw_error,
    )
    if match:
        page_num = match.group(1)
        count = int(match.group(2))
        target_mid = 3387
        if count < 3300:
            add_target = target_mid - count
            return (
                f"{raw_error}\n"
                f"NUMERIC CORRECTION REQUIRED: Page {page_num} has {count} characters (SHORT of 3300 min). "
                f"You MUST expand the resume text by approximately {add_target} characters to land near {target_mid} characters. "
                f"Add 1 technical sentence to 2-3 experience bullets or expand skill elements."
            )
        elif count > 3475:
            trim_target = count - target_mid
            return (
                f"{raw_error}\n"
                f"NUMERIC CORRECTION REQUIRED: Page {page_num} has {count} characters (EXCEEDS 3475 max). "
                f"You MUST trim the resume text by approximately {trim_target} characters to land near {target_mid} characters. "
                f"Slightly shorten 2-3 experience bullets."
            )

    match_final = re.search(
        r"Page (\d+) \(final\) character count \((\d+)\) is less than minimum 1400 characters",
        raw_error,
    )
    if match_final:
        page_num = match_final.group(1)
        count = int(match_final.group(2))
        add_target = 1500 - count
        return (
            f"{raw_error}\n"
            f"NUMERIC CORRECTION REQUIRED: Final Page {page_num} has {count} characters (SHORT of 1400 min). "
            f"You MUST add approximately {add_target} characters across experience/project sections."
        )

    return raw_error


def crewai_generate_resume_with_retry(
    vacancy: "Vacancy",
    evaluation: BasicEvaluationCrewAI,
    *,
    max_retries: int = 1,
) -> tuple[ResumeCrewAI, str]:
    """Generate a resume and render to PDF, making at most max_retries retry with factual layout feedback if page budget fails."""
    import tempfile

    attempts = 0
    max_attempts = max_retries + 1
    layout_feedback = ""
    last_error: Exception | None = None

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
            )
            render_resume_crewai_to_pdf(resume, temp_pdf_path)
            return resume, temp_pdf_path
        except Exception as err:
            last_error = err
            if os.path.exists(temp_pdf_path):
                try:
                    os.remove(temp_pdf_path)
                except OSError:
                    pass

            if attempts < max_attempts:
                layout_feedback = _format_numeric_layout_feedback(str(err))
            else:
                raise last_error from err
