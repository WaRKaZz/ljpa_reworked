import ast
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
from ljpa_reworked.crews.submission_review_crew import SubmissionReviewCrew
from ljpa_reworked.decorators import crewai_retry_handler
from ljpa_reworked.models.crewai_pydantic_models import (
    BasicEvaluationCrewAI,
    EmailCrewAI,  # noqa
    ResumeCrewAI,
    SubmissionReviewCrewAI,
    VisaStatus,
)
from ljpa_reworked.resume_static_profile import (
    merge_static_resume_profile,
    parse_static_resume_profile,
)
from ljpa_reworked.services.rendercv_helper import (
    ResumeLayoutError,
    render_resume_crewai_to_pdf,
)

if TYPE_CHECKING:
    from ljpa_reworked.models.database_models import Vacancy


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
CORE_PROFILE_SECTIONS = {
    "personal_info",
    "summary",
    "experience",
    "education",
    "skills",
}


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


def extract_clean_json(text: str) -> dict:
    """Extract and parse a JSON dictionary from raw LLM output, markdown blocks, or python AST."""
    if not text or not isinstance(text, str):
        raise ValueError("Empty or invalid output from LLM.")
    match = re.search(r"```(?:json|python)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    cleaned = match.group(1).strip() if match else text.strip()
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        try:
            return json.loads(cleaned[first_brace : last_brace + 1])
        except Exception:
            pass
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # AST fallback if model returned Python code/instantiation
    try:
        tree = ast.parse(cleaned)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                payload = {}
                for kw in node.keywords:
                    if kw.arg:
                        payload[kw.arg] = ast.literal_eval(kw.value)
                if payload:
                    return payload
            elif isinstance(node, ast.Dict):
                return ast.literal_eval(node)
    except Exception:
        pass

    raise ValueError(f"Could not extract valid JSON from LLM output: {text[:200]}")


def format_visa_status_context(visa_status: object) -> tuple[str, str]:
    if isinstance(visa_status, VisaStatus):
        status_str = visa_status.value
    elif isinstance(visa_status, str):
        status_str = visa_status.strip()
    else:
        status_str = "not_mentioned"

    status_str_lower = status_str.lower()
    if status_str_lower == "provided":
        context = (
            "The employer explicitly provides visa sponsorship (database visa_status: provided). "
            "Visa sponsorship is confirmed provided by the employer."
        )
    elif status_str_lower == "not_provided":
        context = "The employer explicitly does NOT provide visa sponsorship (database visa_status: not_provided)."
    elif status_str_lower == "not_required":
        context = "Visa sponsorship is not required for this vacancy (database visa_status: not_required)."
    else:
        context = (
            "Visa status is not specified in the database (database visa_status: not_mentioned). "
            "Evaluate feasibility based on vacancy text and secondary factors."
        )
    return status_str, context


@crewai_retry_handler
def crewai_evaluate_vacancy(vacancy: "Vacancy") -> BasicEvaluationCrewAI:
    profile_text = read_profile_text(PROFILE_FILE_PATH)
    present_sections = validate_profile_completeness(profile_text)
    crew = ResumeEvaluationCrew().crew()
    raw_visa_status = getattr(vacancy, "visa_status", None)
    visa_status_val, visa_status_context = format_visa_status_context(raw_visa_status)
    inputs = {
        "text": vacancy.text,
        "title": vacancy.title,
        "submit_email": vacancy.submit_email or "",
        "submit_url": vacancy.submit_url or "",
        "linkedin_url": LINKEDIN_PROFILE_URL,
        "candidate_profile": profile_text,
        "required_profile_sections": present_sections,
        "visa_status": visa_status_val,
        "visa_status_context": visa_status_context,
    }
    crew_output = crew.kickoff(inputs=inputs)
    if isinstance(getattr(crew_output, "pydantic", None), BasicEvaluationCrewAI):
        return crew_output.pydantic.model_copy(update={"missing_mandatory_facts": []})

    merged_data: dict = {}
    tasks_out = getattr(crew_output, "tasks_output", None) or []
    for task_out in tasks_out:
        if isinstance(getattr(task_out, "pydantic", None), BasicEvaluationCrewAI):
            merged_data.update(task_out.pydantic.model_dump())
        else:
            raw_text = getattr(task_out, "raw", "")
            if isinstance(raw_text, str) and raw_text.strip():
                try:
                    data = extract_clean_json(raw_text)
                    if isinstance(data, dict):
                        merged_data.update(data)
                except Exception:
                    pass

    if not merged_data:
        raw_text = getattr(crew_output, "raw", "")
        if isinstance(raw_text, str) and raw_text.strip():
            merged_data = extract_clean_json(raw_text)

    if not merged_data:
        raise ValueError("CrewAI evaluation returned no structured output.")

    if "visa_probability" not in merged_data:
        merged_data["visa_probability"] = 100
    if "missing_mandatory_facts" not in merged_data:
        merged_data["missing_mandatory_facts"] = []

    evaluation = BasicEvaluationCrewAI.model_validate(merged_data)
    # The profile passed the deterministic completeness check above. A vacancy
    # requirement the candidate does not meet affects rating, never profile completeness.
    return evaluation.model_copy(update={"missing_mandatory_facts": []})


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
    raw_text = getattr(crew_output, "raw", "")
    if not raw_text and getattr(crew_output, "tasks_output", None):
        raw_text = getattr(crew_output.tasks_output[-1], "raw", "")
    dynamic_resume = extract_clean_json(raw_text)
    resume = ResumeCrewAI.model_validate(
        merge_static_resume_profile(dynamic_resume, static_profile)
    )
    validate_resume_facts(resume, evaluation, present_sections=present_sections)
    return resume


@crewai_retry_handler
def crewai_generate_email(vacancy: "Vacancy") -> EmailCrewAI:
    profile_text = read_profile_text(PROFILE_FILE_PATH)
    crew = EmailGenerationCrew().crew()
    inputs = {
        "text": vacancy["text"] if isinstance(vacancy, dict) else vacancy.text,
        "title": vacancy["title"] if isinstance(vacancy, dict) else vacancy.title,
        "submit_email": (
            vacancy.get("submit_email") or ""
            if isinstance(vacancy, dict)
            else (vacancy.submit_email or "")
        ),
        "submit_url": (
            vacancy.get("submit_url") or ""
            if isinstance(vacancy, dict)
            else (vacancy.submit_url or "")
        ),
        "candidate_profile": profile_text,
        "email_signature": EMAIL_SIGNATURE,
    }
    crew_output = crew.kickoff(inputs=inputs)
    if isinstance(getattr(crew_output, "pydantic", None), EmailCrewAI):
        return crew_output.pydantic

    tasks_out = getattr(crew_output, "tasks_output", None) or []
    for task_out in tasks_out:
        if isinstance(getattr(task_out, "pydantic", None), EmailCrewAI):
            return task_out.pydantic
        raw_text = getattr(task_out, "raw", "")
        if isinstance(raw_text, str) and raw_text.strip():
            try:
                data = extract_clean_json(raw_text)
                if isinstance(data, dict):
                    return EmailCrewAI.model_validate(data)
            except Exception:
                pass

    raw_text = getattr(crew_output, "raw", "")
    if isinstance(raw_text, str) and raw_text.strip():
        data = extract_clean_json(raw_text)
        if isinstance(data, dict):
            return EmailCrewAI.model_validate(data)

    raise ValueError("CrewAI email returned no structured output.")


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
            if not isinstance(err, ResumeLayoutError):
                if os.path.exists(temp_pdf_path):
                    try:
                        os.remove(temp_pdf_path)
                    except OSError:
                        pass
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


def create_review_crew():
    return SubmissionReviewCrew().crew()


def crewai_review_submission_result(tail_lines: list[str]) -> SubmissionReviewCrewAI:
    """Review stream tail with CrewAI and return structured decision."""
    try:
        stream_tail = "".join(tail_lines)
        crew = create_review_crew()
        crew_output = crew.kickoff(inputs={"stream_tail": stream_tail})
        review = None
        if hasattr(crew_output, "tasks_output") and crew_output.tasks_output:
            review = getattr(crew_output.tasks_output[-1], "pydantic", None)
        if review is None and hasattr(crew_output, "pydantic"):
            review = crew_output.pydantic
        if isinstance(review, SubmissionReviewCrewAI) and review.decision in (
            "success",
            "error",
        ):
            return review
        return SubmissionReviewCrewAI(
            decision="error",
            error_description="CrewAI submission review returned invalid or missing structured result.",
        )
    except Exception as exc:
        return SubmissionReviewCrewAI(
            decision="error",
            error_description=f"Submission review failed: {exc}",
        )
