import re
from enum import Enum
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from ljpa_reworked.models.enums import VacancyStatus as VacancyStatus  # noqa: F401

# Define the string type with whitespace stripping
StrippedStr = Annotated[str, StringConstraints(strip_whitespace=True)]


class VisaStatus(Enum):
    provided = "provided"
    not_provided = "not_provided"
    not_mentioned = "not_mentioned"
    not_required = "not_required"


class PersonalInfoCrewAI(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]
    email: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]
    phone: Annotated[str, StringConstraints(strip_whitespace=True, max_length=20)]
    address: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]


class EducationCrewAI(BaseModel):
    course: StrippedStr
    institution: StrippedStr
    location: StrippedStr
    start_date: StrippedStr
    end_date: StrippedStr


class ExperienceCrewAI(BaseModel):
    title: StrippedStr
    company: StrippedStr
    location: StrippedStr
    start_date: StrippedStr
    end_date: StrippedStr
    description: list[StrippedStr]


class SkillCrewAI(BaseModel):
    title: StrippedStr
    elements: list[StrippedStr]


class ProjectCrewAI(BaseModel):
    title: StrippedStr
    description: StrippedStr


class CertificationCrewAI(BaseModel):
    title: StrippedStr


class ResumeCrewAI(BaseModel):
    personal_info: PersonalInfoCrewAI
    summary: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]
    education: list[EducationCrewAI]
    experience: list[ExperienceCrewAI]
    skills: list[SkillCrewAI]
    projects: list[ProjectCrewAI] = []
    certifications: list[CertificationCrewAI] = []


class VacancyCrewAI(BaseModel):
    title: Annotated[
        str,
        StringConstraints(strip_whitespace=True, max_length=200),
    ]
    text: Annotated[str, StringConstraints(strip_whitespace=True, max_length=3000)]
    submit_email: StrippedStr | None = None
    submit_url: StrippedStr | None = None
    visa_status: VisaStatus
    post_id: int | None = None

    @field_validator("submit_email", "submit_url", mode="before")
    @classmethod
    def empty_string_to_none(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return None
        return v

    @field_validator("submit_email", mode="after")
    @classmethod
    def validate_email_syntax(cls, v):
        if v is not None:
            if not re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", v):
                raise ValueError("Invalid email syntax")
        return v

    @model_validator(mode="after")
    def validate_at_least_one_contact(self):
        email_clean = self.submit_email.strip() if self.submit_email else None
        url_clean = self.submit_url.strip() if self.submit_url else None
        if not email_clean and not url_clean:
            raise ValueError(
                "Vacancy must have at least one contact method (submit_email or submit_url)."
            )
        return self


class EmailCrewAI(BaseModel):
    subject: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
    body: StrippedStr


class BasicEvaluationCrewAI(BaseModel):
    summary: StrippedStr
    rating: Annotated[int, Field(ge=0, le=100)]


class ProcessedPost(BaseModel):
    is_vacancy: bool = Field(
        default=False,
        description="verifies if provided post was job vacancy or not",
    )


class JobSearchQuery(BaseModel):
    search_term: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=2, max_length=160)
    ]
    location: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=2, max_length=160)
    ]
    site_name: Literal["linkedin", "indeed", "glassdoor", "google", "zip_recruiter"]
    results_wanted: Annotated[int, Field(ge=1, le=50)] = 25


class JobSearchQuerySet(BaseModel):
    profile_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    queries: Annotated[list[JobSearchQuery], Field(min_length=1, max_length=12)]

    @model_validator(mode="after")
    def reject_normalized_duplicates(self):
        keys = {
            (query.site_name, query.search_term.casefold(), query.location.casefold())
            for query in self.queries
        }
        if len(keys) != len(self.queries):
            raise ValueError("duplicate normalized job search queries are not allowed")
        return self
