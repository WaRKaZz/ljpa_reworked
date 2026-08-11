from ljpa_reworked.models.crewai_pydantic_models import (
    EducationCrewAI,
    ExperienceCrewAI,
    PersonalInfoCrewAI,
    ResumeCrewAI,
    SkillCrewAI,
)
from ljpa_reworked.services.rendercv_helper import (
    convert_resume_crewai_to_rendercv_input,
)


def test_education_and_experience_use_normal_entry_layout():
    resume = ResumeCrewAI(
        personal_info=PersonalInfoCrewAI(
            name="Test", email="test@example.com", phone="+1 555 0100",
            address="Berlin", location="Berlin",
        ),
        summary="Test summary",
        education=[EducationCrewAI(course="BSc", institution="University", location="Berlin", start_date="2016", end_date="2020")],
        experience=[ExperienceCrewAI(title="Engineer", company="Company", location="Berlin", start_date="2020", end_date="Present", description=["One", "Two", "Three"])],
        skills=[SkillCrewAI(title="Skills", elements=["PLC"])],
    )

    sections = convert_resume_crewai_to_rendercv_input(resume)["cv"]["sections"]
    assert sections["Education"][0]["name"] == "University — BSc"
    assert sections["Education"][0]["summary"] == "Berlin"
    assert "institution" not in sections["Education"][0]
    assert sections["Experience"][0]["name"] == "Company — Engineer"
    assert sections["Experience"][0]["summary"] == "Berlin"
    assert "company" not in sections["Experience"][0]
