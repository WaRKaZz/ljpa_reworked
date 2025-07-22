from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

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
    url: StrippedStr | None = None
    credentials: Annotated[
        str, StringConstraints(strip_whitespace=True, max_length=500)
    ]
    visa_status: VisaStatus
    post_id: int | None = None


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
