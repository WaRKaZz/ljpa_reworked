import re
from typing import Any

from ljpa_reworked.models.crewai_pydantic_models import ResumeCrewAI


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
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
        parsed_us = phonenumbers.parse(phone_clean, "US")
        if phonenumbers.is_valid_number(parsed_us):
            return phonenumbers.format_number(parsed_us, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
    except Exception:
        pass
    return None


def convert_resume_crewai_to_rendercv_input(resume: ResumeCrewAI) -> dict[str, Any]:
    """Convert a ResumeCrewAI model into a RenderCV input dictionary."""
    info = resume.personal_info

    cv: dict[str, Any] = {
        "name": info.name,
    }
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
            skill_entries.append({
                "label": skill.title,
                "details": ", ".join(skill.elements),
            })
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
    return {"cv": cv}


def validate_pdf_page_layout(pdf_path: str) -> tuple[bool, str]:
    """Validate PDF page count and layout fill requirements.

    Max 2 pages; page 2 allowed only if it contains secondary material and is at least 50% filled.
    """
    import os
    if not os.path.exists(pdf_path):
        return False, f"PDF file does not exist at {pdf_path}"

    try:
        import pypdfium2
        doc = pypdfium2.PdfDocument(pdf_path)
    except Exception as e:
        return False, f"Failed to parse PDF: {e}"

    num_pages = len(doc)
    if num_pages == 1:
        return True, "1-page PDF meets layout requirements"
    elif num_pages > 2:
        return False, f"PDF exceeds maximum 2 pages: total {num_pages} pages"

    page2 = doc[1]
    w, h = page2.get_size()
    text = page2.get_textpage().get_text_range()

    secondary_keywords = ["certifications", "projects", "education", "tools", "skills", "languages", "courses", "certificates"]
    has_secondary = any(kw in text.lower() for kw in secondary_keywords)
    if not has_secondary:
        return False, "Page 2 lacks secondary section content"

    import numpy as np
    image = page2.render(scale=1).to_pil()
    img_arr = np.array(image.convert("L"))
    mask = img_arr < 240
    y_indices, _ = np.where(mask)
    if len(y_indices) == 0:
        return False, "Page 2 is empty"

    max_y = y_indices.max()
    fill_pct = max_y / h
    if fill_pct < 0.50:
        return False, f"Page 2 fill level ({fill_pct*100:.1f}%) is less than 50%"

    return True, f"2-page PDF valid with secondary material and {fill_pct*100:.1f}% fill on page 2"


def render_resume_crewai_to_pdf(resume: ResumeCrewAI, output_pdf_path: str) -> str:
    """Convert a ResumeCrewAI model to RenderCV input YAML and render a PDF using RenderCV."""
    import os
    import subprocess
    import tempfile

    import yaml

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
        res = subprocess.run(cmd, capture_output=True, text=True, cwd=temp_dir)
        if res.returncode != 0 or not os.path.exists(output_pdf_path):
            raise RuntimeError(
                f"RenderCV rendering failed with exit code {res.returncode}: {res.stderr}\n{res.stdout}"
            )

    is_valid, msg = validate_pdf_page_layout(output_pdf_path)
    if not is_valid:
        if os.path.exists(output_pdf_path):
            try:
                os.remove(output_pdf_path)
            except OSError:
                pass
        raise RuntimeError(f"RenderCV output failed page layout validation: {msg}")

    return output_pdf_path
