from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum


class CanonicalField(StrEnum):
    FIRST_NAME = "first_name"
    LAST_NAME = "last_name"
    FULL_NAME = "full_name"
    MIDDLE_NAME = "middle_name"
    EMAIL = "email"
    CONFIRM_EMAIL = "confirm_email"
    PHONE = "phone"
    PHONE_COUNTRY_CODE = "phone_country_code"
    NATIONAL_PHONE = "national_phone"
    COUNTRY = "country"
    CITY = "city"
    LOCATION = "location"
    POSTAL_CODE = "postal_code"
    ADDRESS = "address"
    LINKEDIN = "linkedin"
    GITHUB = "github"
    PORTFOLIO = "portfolio"
    WEBSITE = "website"
    CURRENT_TITLE = "current_title"
    CURRENT_COMPANY = "current_company"
    EXPERIENCE_YEARS = "experience_years"
    WORK_AUTHORIZATION = "work_authorization"
    REQUIRES_SPONSORSHIP = "requires_sponsorship"
    WILLING_TO_RELOCATE = "willing_to_relocate"
    NOTICE_PERIOD = "notice_period"
    DESIRED_SALARY = "desired_salary"
    RESUME = "resume"
    COVER_LETTER = "cover_letter"


@dataclass
class FieldRule:
    canonical: CanonicalField
    autocomplete: list[str] = field(default_factory=list)
    names: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    placeholders: list[str] = field(default_factory=list)
    types: list[str] = field(default_factory=list)


# General negative keywords that indicate third-party / non-candidate context
NEGATIVE_CONTEXT_PATTERNS = [
    r"\bmanager\b",
    r"\breferral\b",
    r"\breferrer\b",
    r"\breference\b",
    r"\bemergency\b",
    r"\bprevious employer\b",
    r"\bspouse\b",
    r"\bfather\b",
    r"\bmother\b",
    r"\bcolleague\b",
    r"\brecommender\b",
    r"\bsupervisor\b",
]

CANONICAL_REGISTRY: dict[CanonicalField, FieldRule] = {
    CanonicalField.FIRST_NAME: FieldRule(
        canonical=CanonicalField.FIRST_NAME,
        autocomplete=["given-name"],
        names=["firstname", "first_name", "fname", "givenname", "legalfirstname"],
        labels=["first name", "given name", "legal first name", "forename", "first"],
        placeholders=["first name", "given name", "john"],
    ),
    CanonicalField.LAST_NAME: FieldRule(
        canonical=CanonicalField.LAST_NAME,
        autocomplete=["family-name"],
        names=[
            "lastname",
            "last_name",
            "lname",
            "surname",
            "familyname",
            "legallastname",
        ],
        labels=["last name", "family name", "surname", "legal last name", "last"],
        placeholders=["last name", "family name", "surname", "doe"],
    ),
    CanonicalField.FULL_NAME: FieldRule(
        canonical=CanonicalField.FULL_NAME,
        autocomplete=["name"],
        names=["fullname", "full_name", "candidate_name", "applicant_name"],
        labels=["full name", "your name", "candidate name", "applicant name", "name"],
        placeholders=["full name", "john doe"],
    ),
    CanonicalField.MIDDLE_NAME: FieldRule(
        canonical=CanonicalField.MIDDLE_NAME,
        autocomplete=["additional-name"],
        names=["middlename", "middle_name", "mname", "middleinitial"],
        labels=["middle name", "middle initial", "additional name"],
        placeholders=["middle name"],
    ),
    CanonicalField.EMAIL: FieldRule(
        canonical=CanonicalField.EMAIL,
        autocomplete=["email"],
        names=["email", "emailaddress", "candidate_email", "applicant_email", "e_mail"],
        labels=["email", "email address", "e-mail", "e-mail address", "primary email"],
        placeholders=["email", "email address", "example@domain.com"],
        types=["email"],
    ),
    CanonicalField.CONFIRM_EMAIL: FieldRule(
        canonical=CanonicalField.CONFIRM_EMAIL,
        autocomplete=[],
        names=["confirmemail", "confirm_email", "verifyemail", "reenteremail"],
        labels=[
            "confirm email",
            "confirm email address",
            "re-enter email",
            "verify email",
        ],
        placeholders=["confirm email", "re-enter email"],
        types=["email"],
    ),
    CanonicalField.PHONE: FieldRule(
        canonical=CanonicalField.PHONE,
        autocomplete=["tel", "tel-national"],
        names=[
            "phone",
            "phonenumber",
            "telephone",
            "mobile",
            "mobilenumber",
            "cellphone",
            "contactnumber",
        ],
        labels=[
            "phone",
            "phone number",
            "telephone",
            "mobile phone",
            "cell phone",
            "contact number",
            "primary phone",
        ],
        placeholders=["phone", "phone number", "mobile", "+1 (555)..."],
        types=["tel"],
    ),
    CanonicalField.PHONE_COUNTRY_CODE: FieldRule(
        canonical=CanonicalField.PHONE_COUNTRY_CODE,
        autocomplete=["tel-country-code"],
        names=["phonecountrycode", "dialcode", "countrydialcode"],
        labels=["phone country code", "country code", "dialing code"],
    ),
    CanonicalField.COUNTRY: FieldRule(
        canonical=CanonicalField.COUNTRY,
        autocomplete=["country-name", "country"],
        names=["country", "countryname", "residencecountry", "territory"],
        labels=["country", "country of residence", "territory", "residence country"],
        placeholders=["country", "select country"],
    ),
    CanonicalField.CITY: FieldRule(
        canonical=CanonicalField.CITY,
        autocomplete=["address-level2"],
        names=["city", "town", "municipality"],
        labels=["city", "town", "municipality", "city of residence"],
        placeholders=["city", "town"],
    ),
    CanonicalField.LOCATION: FieldRule(
        canonical=CanonicalField.LOCATION,
        autocomplete=[],
        names=["location", "citystate", "citycountry"],
        labels=["location", "city, state", "city / country", "current location"],
        placeholders=["city, state", "location"],
    ),
    CanonicalField.POSTAL_CODE: FieldRule(
        canonical=CanonicalField.POSTAL_CODE,
        autocomplete=["postal-code"],
        names=["postalcode", "postal_code", "zipcode", "zip_code", "zip", "postcode"],
        labels=["postal code", "zip code", "postcode", "zip", "postal / zip code"],
        placeholders=["postal code", "zip code", "zip"],
    ),
    CanonicalField.ADDRESS: FieldRule(
        canonical=CanonicalField.ADDRESS,
        autocomplete=["street-address", "address-line1"],
        names=["address", "address1", "addressline1", "streetaddress", "street"],
        labels=["address", "street address", "address line 1", "home address"],
        placeholders=["street address", "address line 1"],
    ),
    CanonicalField.LINKEDIN: FieldRule(
        canonical=CanonicalField.LINKEDIN,
        autocomplete=[],
        names=["linkedin", "linkedinurl", "linkedin_profile", "linkedinlink"],
        labels=[
            "linkedin",
            "linkedin url",
            "linkedin profile",
            "linkedin profile url",
            "linkedin link",
        ],
        placeholders=["linkedin.com/in/...", "https://linkedin.com/in/"],
        types=["url"],
    ),
    CanonicalField.GITHUB: FieldRule(
        canonical=CanonicalField.GITHUB,
        autocomplete=[],
        names=["github", "githuburl", "github_profile", "githublink"],
        labels=[
            "github",
            "github url",
            "github profile",
            "github profile url",
            "github link",
        ],
        placeholders=["github.com/...", "https://github.com/"],
        types=["url"],
    ),
    CanonicalField.PORTFOLIO: FieldRule(
        canonical=CanonicalField.PORTFOLIO,
        autocomplete=[],
        names=["portfolio", "portfoliourl", "personalwebsite"],
        labels=[
            "portfolio",
            "portfolio url",
            "personal website",
            "portfolio link",
            "personal portfolio",
        ],
        placeholders=["portfolio url", "personal website"],
        types=["url"],
    ),
    CanonicalField.WEBSITE: FieldRule(
        canonical=CanonicalField.WEBSITE,
        autocomplete=["url"],
        names=["website", "websiteurl", "blog", "homepage"],
        labels=["website", "website url", "web site", "personal site", "blog"],
        placeholders=["https://...", "website"],
        types=["url"],
    ),
    CanonicalField.CURRENT_TITLE: FieldRule(
        canonical=CanonicalField.CURRENT_TITLE,
        autocomplete=["organization-title"],
        names=["currenttitle", "jobtitle", "title", "currentrole", "designation"],
        labels=[
            "current job title",
            "current title",
            "current role",
            "job title",
            "title",
            "designation",
        ],
        placeholders=["software engineer", "job title"],
    ),
    CanonicalField.CURRENT_COMPANY: FieldRule(
        canonical=CanonicalField.CURRENT_COMPANY,
        autocomplete=["organization"],
        names=["currentcompany", "company", "employer", "currentemployer"],
        labels=[
            "current company",
            "current employer",
            "company name",
            "employer",
            "company",
        ],
        placeholders=["company name", "current employer"],
    ),
    CanonicalField.EXPERIENCE_YEARS: FieldRule(
        canonical=CanonicalField.EXPERIENCE_YEARS,
        autocomplete=[],
        names=["experienceyears", "yearsexperience", "totalexperience"],
        labels=[
            "years of experience",
            "total experience",
            "years of relevant experience",
        ],
    ),
    CanonicalField.WORK_AUTHORIZATION: FieldRule(
        canonical=CanonicalField.WORK_AUTHORIZATION,
        autocomplete=[],
        names=["workauth", "workauthorization", "authorizedtowork"],
        labels=[
            "are you authorized to work",
            "work authorization",
            "legally authorized to work",
            "right to work",
        ],
    ),
    CanonicalField.REQUIRES_SPONSORSHIP: FieldRule(
        canonical=CanonicalField.REQUIRES_SPONSORSHIP,
        autocomplete=[],
        names=["requiresponsorship", "visasponsorship", "needvisa"],
        labels=[
            "will you require sponsorship",
            "do you require visa sponsorship",
            "sponsorship requirement",
            "will you now or in the future require sponsorship",
            "visa sponsorship",
        ],
    ),
    CanonicalField.WILLING_TO_RELOCATE: FieldRule(
        canonical=CanonicalField.WILLING_TO_RELOCATE,
        autocomplete=[],
        names=["willingtorelocate", "relocation", "openrelocation"],
        labels=[
            "willing to relocate",
            "are you willing to relocate",
            "open to relocation",
            "relocation",
        ],
    ),
    CanonicalField.NOTICE_PERIOD: FieldRule(
        canonical=CanonicalField.NOTICE_PERIOD,
        autocomplete=[],
        names=["noticeperiod", "availability", "startdate"],
        labels=[
            "notice period",
            "how soon can you start",
            "availability",
            "available to start",
            "earliest start date",
        ],
    ),
    CanonicalField.DESIRED_SALARY: FieldRule(
        canonical=CanonicalField.DESIRED_SALARY,
        autocomplete=[],
        names=["desiredsalary", "expectedsalary", "salaryexpectation", "salary"],
        labels=[
            "desired salary",
            "salary expectation",
            "expected compensation",
            "expected annual salary",
            "salary expectations",
        ],
        placeholders=["e.g. 75000", "desired salary"],
    ),
    CanonicalField.RESUME: FieldRule(
        canonical=CanonicalField.RESUME,
        autocomplete=[],
        names=["resume", "cv", "resumefile", "cvfile", "attachment", "resumeupload"],
        labels=[
            "resume",
            "cv",
            "upload resume",
            "attach resume",
            "attach cv",
            "upload cv",
            "curriculum vitae",
        ],
        types=["file"],
    ),
    CanonicalField.COVER_LETTER: FieldRule(
        canonical=CanonicalField.COVER_LETTER,
        autocomplete=[],
        names=[
            "coverletter",
            "cover_letter",
            "hiringmanagermessage",
            "messagetohiringteam",
        ],
        labels=[
            "cover letter",
            "message to the hiring team",
            "message to recruiter",
            "additional comments",
            "note to hiring manager",
        ],
    ),
}


def _normalize_string(val: str | None) -> str:
    if not val:
        return ""
    return re.sub(r"[^a-z0-9]", "", val.lower())


def _has_negative_context(text: str) -> bool:
    if not text:
        return False
    lower = text.lower()
    return any(re.search(pat, lower) for pat in NEGATIVE_CONTEXT_PATTERNS)


def classify_control(
    control: dict[str, str | None],
) -> tuple[CanonicalField | None, float]:
    """Evaluate visible control metadata against canonical registry using weighted scoring."""
    ctype = (control.get("type") or "").lower()
    autocomplete = (control.get("autocomplete") or "").lower().strip()
    label = (control.get("label") or "").strip()
    aria_label = (control.get("aria_label") or "").strip()
    name = (control.get("name") or "").strip()
    cid = (control.get("id") or "").strip()
    placeholder = (control.get("placeholder") or "").strip()

    # Check negative context across all textual signals
    combined_text = f"{label} {aria_label} {name} {cid} {placeholder}"
    if _has_negative_context(combined_text):
        return None, 0.0

    # Special handling for file input (Resume / CV)
    if ctype == "file":
        norm_combined = _normalize_string(combined_text)
        if any(
            k in norm_combined
            for k in ("resume", "cv", "curriculumvitae", "dropzone", "upload")
        ):
            return CanonicalField.RESUME, 0.95
        return CanonicalField.RESUME, 0.85

    norm_autocomplete = _normalize_string(autocomplete)
    norm_label = _normalize_string(label)
    norm_aria = _normalize_string(aria_label)
    norm_name = _normalize_string(name)
    norm_id = _normalize_string(cid)
    norm_placeholder = _normalize_string(placeholder)

    best_match: CanonicalField | None = None
    highest_score = 0.0

    for canonical, rule in CANONICAL_REGISTRY.items():
        score = 0.0

        # Autocomplete signal (weight 1.0)
        if autocomplete:
            for ac in rule.autocomplete:
                if ac in autocomplete or _normalize_string(ac) == norm_autocomplete:
                    score += 1.0
                    break

        # Explicit label signal (weight 0.85)
        if label:
            for lbl in rule.labels:
                norm_lbl = _normalize_string(lbl)
                if norm_lbl:
                    if norm_lbl == norm_label:
                        score += 0.85
                        break
                    elif norm_lbl in norm_label:
                        score += 0.75
                        break

        # Aria-label signal (weight 0.8)
        if aria_label and not label:
            for lbl in rule.labels:
                norm_lbl = _normalize_string(lbl)
                if norm_lbl:
                    if norm_lbl == norm_aria:
                        score += 0.8
                        break
                    elif norm_lbl in norm_aria:
                        score += 0.7
                        break

        # Name signal (weight 0.7)
        if name:
            for nm in rule.names:
                norm_nm = _normalize_string(nm)
                if norm_nm:
                    if norm_nm == norm_name:
                        score += 0.7
                        break
                    elif norm_nm in norm_name:
                        score += 0.65
                        break

        # ID signal (weight 0.6)
        if cid and not name:
            for nm in rule.names:
                norm_nm = _normalize_string(nm)
                if norm_nm and norm_nm in norm_id:
                    score += 0.6
                    break

        # Placeholder signal (weight 0.5)
        if placeholder:
            for pl in rule.placeholders:
                norm_pl = _normalize_string(pl)
                if norm_pl:
                    if norm_pl == norm_placeholder:
                        score += 0.5
                        break
                    elif norm_pl in norm_placeholder:
                        score += 0.4
                        break

        # Boost if explicit input type matches rule
        if ctype and rule.types and ctype in rule.types:
            score += 0.1

        # Distinguish first_name / last_name from full_name if both matched
        if canonical == CanonicalField.FULL_NAME and (
            "first" in combined_text.lower() or "last" in combined_text.lower()
        ):
            score *= 0.5

        # Normalize score upper bound to 1.0
        score = min(1.0, score)

        if score > highest_score:
            highest_score = score
            best_match = canonical

    # Threshold for confident deterministic fill
    if highest_score >= 0.70:
        return best_match, highest_score

    return None, highest_score
