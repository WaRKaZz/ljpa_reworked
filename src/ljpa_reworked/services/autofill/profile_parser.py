from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CandidateProfile:
    first_name: str = ""
    last_name: str = ""
    full_name: str = ""
    middle_name: str = ""
    email: str = ""
    phone: str = ""
    phone_country_code: str = "+7"
    national_phone: str = ""
    country: str = ""
    city: str = ""
    location: str = ""
    postal_code: str = ""
    address: str = ""
    linkedin: str = ""
    github: str = ""
    portfolio: str = ""
    website: str = ""
    target_title: str = ""
    current_title: str = ""
    current_company: str = ""
    experience_years: int = 0
    work_authorization: str = ""
    requires_sponsorship: bool = True
    willing_to_relocate: bool = True
    notice_period: str = "1 month"
    desired_salary: str = ""
    skills: list[str] = field(default_factory=list)
    languages: dict[str, str] = field(default_factory=dict)
    summary: str = ""

    def get_canonical_value(self, canonical_name: str) -> str | bool | int | None:
        """Map canonical field name to candidate profile attribute."""
        mapping = {
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": self.full_name,
            "middle_name": self.middle_name,
            "email": self.email,
            "confirm_email": self.email,
            "phone": self.phone,
            "phone_country_code": self.phone_country_code,
            "national_phone": self.national_phone,
            "country": self.country,
            "city": self.city,
            "location": self.location,
            "postal_code": self.postal_code,
            "address": self.address,
            "linkedin": self.linkedin,
            "github": self.github,
            "portfolio": self.portfolio,
            "website": self.website or self.portfolio or self.linkedin,
            "target_title": self.target_title,
            "current_title": self.current_title,
            "current_company": self.current_company,
            "experience_years": self.experience_years,
            "work_authorization": self.work_authorization,
            "requires_sponsorship": self.requires_sponsorship,
            "willing_to_relocate": self.willing_to_relocate,
            "notice_period": self.notice_period,
            "desired_salary": self.desired_salary,
        }
        return mapping.get(canonical_name)


def parse_profile_markdown(text: str) -> CandidateProfile:
    """Parse profile.md markdown text into a structured CandidateProfile instance."""
    profile = CandidateProfile()

    # Name
    name_match = re.search(r"\*\*Name:\*\*\s*([^\n\r]+)", text, re.IGNORECASE)
    if name_match:
        full_name = name_match.group(1).strip()
        profile.full_name = full_name
        parts = full_name.split()
        if len(parts) == 1:
            profile.first_name = parts[0]
        elif len(parts) >= 2:
            profile.first_name = parts[0]
            profile.last_name = parts[-1]
            if len(parts) > 2:
                profile.middle_name = " ".join(parts[1:-1])

    # Target Title
    title_match = re.search(r"\*\*Target Title:\*\*\s*([^\n\r]+)", text, re.IGNORECASE)
    if title_match:
        profile.target_title = title_match.group(1).strip()

    # Location
    loc_match = re.search(r"\*\*Location:\*\*\s*([^\n\r]+)", text, re.IGNORECASE)
    if loc_match:
        loc_str = loc_match.group(1).strip()
        profile.location = loc_str
        loc_parts = [p.strip() for p in loc_str.split(",")]
        if len(loc_parts) >= 2:
            profile.city = loc_parts[0]
            profile.country = loc_parts[-1]
        elif len(loc_parts) == 1:
            profile.city = loc_parts[0]

    # Email
    email_match = re.search(r"\*\*Email:\*\*\s*([^\n\r\s]+)", text, re.IGNORECASE)
    if email_match:
        profile.email = email_match.group(1).strip()

    # Phone
    phone_match = re.search(r"\*\*Phone:\*\*\s*([^\n\r]+)", text, re.IGNORECASE)
    if phone_match:
        raw_phone = phone_match.group(1).strip()
        profile.phone = raw_phone
        digits = re.sub(r"\D", "", raw_phone)
        if raw_phone.startswith("+7") or raw_phone.startswith("7"):
            profile.phone_country_code = "+7"
            profile.national_phone = digits[1:] if len(digits) > 10 else digits
        elif raw_phone.startswith("+"):
            profile.phone_country_code = raw_phone.split()[0]
            profile.national_phone = digits[len(profile.phone_country_code) - 1 :]
        else:
            profile.national_phone = digits

    # LinkedIn
    li_match = re.search(r"\*\*LinkedIn:\*\*\s*([^\n\r\s]+)", text, re.IGNORECASE)
    if li_match:
        profile.linkedin = li_match.group(1).strip()

    # GitHub
    gh_match = re.search(r"\*\*GitHub:\*\*\s*([^\n\r\s]+)", text, re.IGNORECASE)
    if gh_match:
        profile.github = gh_match.group(1).strip()

    # Portfolio / Website
    site_match = re.search(
        r"\*\*(?:Portfolio|Website|Portfolio\s*/\s*Website):\*\*\s*([^\n\r\s]+)",
        text,
        re.IGNORECASE,
    )
    if site_match:
        profile.portfolio = site_match.group(1).strip()
        profile.website = site_match.group(1).strip()

    # Work Authorization & Sponsorship
    auth_match = re.search(
        r"\*\*Citizenship & Work Authorization:\*\*\s*([^\n\r]+)", text, re.IGNORECASE
    )
    if auth_match:
        profile.work_authorization = auth_match.group(1).strip()

    spons_match = re.search(
        r"\*\*Visa Sponsorship Requirement:\*\*\s*([^\n\r]+)", text, re.IGNORECASE
    )
    if spons_match:
        spons_text = spons_match.group(1).lower()
        profile.requires_sponsorship = (
            "require" in spons_text or "strict requirement" in spons_text
        )

    # Years of experience from summary or experience section
    exp_years_match = re.search(r"(\d+)\+?\s+years of experience", text, re.IGNORECASE)
    if exp_years_match:
        profile.experience_years = int(exp_years_match.group(1))

    # Experience section: latest job
    exp_heading_match = re.search(
        r"###\s+([^\n\r—\-]+)\s+[—\-]\s+([^\n\r]+)", text, re.IGNORECASE
    )
    if exp_heading_match:
        profile.current_company = exp_heading_match.group(1).strip()
        profile.current_title = exp_heading_match.group(2).strip()

    return profile


def load_candidate_profile(path: Path | str) -> CandidateProfile:
    """Load and parse CandidateProfile from given file path."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Profile file not found at: {path}")
    content = p.read_text(encoding="utf-8")
    return parse_profile_markdown(content)
