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
    if date_clean.lower() == "present":
        return "present"
    return date_clean


def convert_resume_crewai_to_rendercv_input(resume: ResumeCrewAI) -> dict[str, Any]:
    """Convert a ResumeCrewAI model into a RenderCV input dictionary."""
    info = resume.personal_info

    cv: dict[str, Any] = {
        "name": info.name,
    }
    if info.email:
        cv["email"] = info.email
    if info.phone:
        cv["phone"] = info.phone
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
            entry: dict[str, Any] = {
                "institution": edu.institution,
                "area": edu.course,
                "location": edu.location,
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
            entry: dict[str, Any] = {
                "company": exp.company,
                "position": exp.title,
                "location": exp.location,
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

    cv["sections"] = sections
    return {"cv": cv}
