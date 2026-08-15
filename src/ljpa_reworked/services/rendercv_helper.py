import re
import warnings
from subprocess import TimeoutExpired
from typing import Any

import pypdfium2

from ljpa_reworked.models.crewai_pydantic_models import ResumeCrewAI

warnings.filterwarnings(
    "ignore",
    message=r"get_text_range\(\) call with default params will be implicitly redirected to get_text_bounded\(\)",
    category=UserWarning,
    module=r"pypdfium2\._helpers\.textpage",
)


def _extract_linkedin_username(url: str | None) -> str | None:
    if not url:
        return None
    url = url.strip()
    match = re.search(r"linkedin\.com/in/([^/]+)", url)
    if match:
        return match.group(1)
    return url


def _normalize_date(date_str: str | None) -> str | None:
    if not date_str:
        return None
    date_clean = date_str.strip()
    if date_clean.lower() in ("present", "current", "now", "ongoing"):
        return "present"
    if re.match(r"^\d{4}(-\d{2})?(-\d{2})?$", date_clean):
        return date_clean
    year_match = re.search(r"\b(19|20)\d{2}\b", date_clean)
    if year_match:
        return year_match.group(0)
    return None


def _normalize_phone(phone_str: str | None) -> str | None:
    if not phone_str:
        return None
    phone_clean = phone_str.strip()
    try:
        import phonenumbers

        parsed = phonenumbers.parse(phone_clean, None)
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL
            )
        parsed_us = phonenumbers.parse(phone_clean, "US")
        if phonenumbers.is_valid_number(parsed_us):
            return phonenumbers.format_number(
                parsed_us, phonenumbers.PhoneNumberFormat.INTERNATIONAL
            )
    except Exception:
        pass
    return None


def convert_resume_crewai_to_rendercv_input(resume: ResumeCrewAI) -> dict[str, Any]:
    """Convert a ResumeCrewAI model into a RenderCV input dictionary."""
    info = resume.personal_info

    cv: dict[str, Any] = {
        "name": info.name,
    }
    if info.target_title:
        cv["headline"] = info.target_title
    if info.email:
        cv["email"] = info.email
    phone = _normalize_phone(info.phone)
    if phone:
        cv["phone"] = phone
    if info.location:
        cv["location"] = info.location

    if info.linkedin_url:
        username = _extract_linkedin_username(info.linkedin_url)
        if username:
            cv["social_networks"] = [{"network": "LinkedIn", "username": username}]

    sections: dict[str, list[Any]] = {}

    if resume.summary:
        sections["Summary"] = [resume.summary]

    if resume.education:
        edu_entries = []
        for edu in resume.education:
            # ponytail: RenderCV EducationEntry reserves columns for institution,
            # area, location, and dates; NormalEntry matches the compact project layout.
            entry: dict[str, Any] = {
                "name": f"{edu.institution} — {edu.course}",
                "summary": edu.location,
            }
            if edu.start_date:
                entry["start_date"] = _normalize_date(edu.start_date)
            if edu.end_date:
                entry["end_date"] = _normalize_date(edu.end_date)
            edu_entries.append(entry)
        sections["Education"] = edu_entries

    if resume.experience:
        exp_entries = []
        for exp in resume.experience:
            # ponytail: NormalEntry avoids the wide ExperienceEntry header table.
            entry: dict[str, Any] = {
                "name": f"{exp.company} — {exp.title}",
                "summary": exp.location,
            }
            if exp.start_date:
                entry["start_date"] = _normalize_date(exp.start_date)
            if exp.end_date:
                entry["end_date"] = _normalize_date(exp.end_date)
            if exp.description:
                entry["highlights"] = exp.description
            exp_entries.append(entry)
        sections["Experience"] = exp_entries

    if resume.skills:
        skill_entries = []
        for skill in resume.skills:
            skill_entries.append(
                {
                    "label": skill.title,
                    "details": ", ".join(skill.elements),
                }
            )
        sections["Skills"] = skill_entries

    if resume.projects:
        proj_entries = []
        for proj in resume.projects:
            entry: dict[str, Any] = {
                "name": proj.title,
                "summary": proj.description,
            }
            if proj.url:
                entry["url"] = proj.url
            if proj.start_date:
                entry["start_date"] = _normalize_date(proj.start_date)
            if proj.end_date:
                entry["end_date"] = _normalize_date(proj.end_date)
            if proj.highlights:
                entry["highlights"] = proj.highlights
            proj_entries.append(entry)
        sections["Projects"] = proj_entries

    if resume.certifications:
        cert_entries = []
        for cert in resume.certifications:
            entry: dict[str, Any] = {
                "name": cert.title,
            }
            if cert.issuer:
                entry["issuer"] = cert.issuer
            if cert.date:
                entry["date"] = _normalize_date(cert.date)
            if cert.url:
                entry["url"] = cert.url
            cert_entries.append(entry)
        sections["Certifications"] = cert_entries

    # HR scans Summary and Skills first; keep ATS-standard sections in this order.
    section_order = (
        "Summary",
        "Skills",
        "Experience",
        "Education",
        "Certifications",
        "Projects",
    )
    cv["sections"] = {
        name: sections[name] for name in section_order if name in sections
    }
    return {
        "cv": cv,
        "design": {
            "theme": "classic",
            # RenderCV 2.8 renamed the per-entry page-break setting.
            "entries": {"allow_page_break": False},
        },
    }


def validate_pdf_page_layout(pdf_path: str) -> tuple[bool, str]:
    """Reject malformed, blank, or unexpectedly long RenderCV PDFs.

    ponytail: extracted-character density is not visual layout. Keep only a
    readable-page floor and the product's two-page ceiling; upgrade to a
    renderer-native box/layout API when RenderCV exposes one.
    """
    import os

    if not os.path.exists(pdf_path):
        return False, f"PDF file does not exist at {pdf_path}"

    try:
        doc = pypdfium2.PdfDocument(pdf_path)
    except Exception as error:
        return False, f"Failed to parse PDF: {error}"

    page_count = len(doc)
    if not 1 <= page_count <= 2:
        return False, f"PDF must contain one or two pages, got {page_count}"

    for index in range(page_count):
        text = doc[index].get_textpage().get_text_bounded().strip()
        if len(text) < 100:
            return False, f"Page {index + 1} has insufficient readable text"

    return True, f"{page_count}-page PDF has readable text on every page"


class RenderCVError(RuntimeError):
    """RenderCV could not produce a PDF."""


class ResumeLayoutError(RenderCVError):
    """A rendered PDF violates deterministic layout requirements."""


def render_resume_crewai_to_pdf(resume: ResumeCrewAI, output_pdf_path: str) -> str:
    """Convert a ResumeCrewAI model to RenderCV input YAML and render a PDF using RenderCV."""
    import os
    import subprocess
    import tempfile

    import yaml

    output_pdf_path = os.path.abspath(output_pdf_path)
    input_dict = convert_resume_crewai_to_rendercv_input(resume)
    # ponytail: RenderCV always creates an output folder; isolate it in a temp dir.
    with tempfile.TemporaryDirectory(prefix="rendercv-") as temp_dir:
        temp_yaml_path = os.path.join(temp_dir, "resume.yaml")
        with open(temp_yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(input_dict, f, allow_unicode=True, sort_keys=False)
        cmd = [
            "rendercv",
            "render",
            temp_yaml_path,
            "--pdf-path",
            output_pdf_path,
            "--dont-generate-markdown",
            "--dont-generate-html",
            "--dont-generate-png",
        ]
        try:
            res = subprocess.run(
                cmd, capture_output=True, text=True, cwd=temp_dir, timeout=120
            )
        except TimeoutExpired as error:
            raise RenderCVError(
                "RenderCV rendering timed out after 120 seconds"
            ) from error
        if res.returncode != 0 or not os.path.exists(output_pdf_path):
            raise RenderCVError(
                f"RenderCV rendering failed with exit code {res.returncode}"
            )

    is_valid, msg = validate_pdf_page_layout(output_pdf_path)
    if not is_valid:
        if os.path.exists(output_pdf_path):
            try:
                os.remove(output_pdf_path)
            except OSError:
                pass
        raise ResumeLayoutError(f"RenderCV output failed page layout validation: {msg}")

    return output_pdf_path
