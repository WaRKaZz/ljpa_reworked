from unittest.mock import MagicMock, patch

import pytest

from ljpa_reworked.crew_workflow import (
    crewai_evaluate_vacancy,
    crewai_generate_resume,
    parse_profile_sections,
    validate_profile_completeness,
    validate_resume_facts,
)
from ljpa_reworked.models.crewai_pydantic_models import (
    BasicEvaluationCrewAI,
    EducationCrewAI,
    ExperienceCrewAI,
    PersonalInfoCrewAI,
    ResumeCrewAI,
    SkillCrewAI,
)


def test_parse_profile_sections_heading_aliases():
    """Verify heading parser extracts aliases and maps to canonical section names."""
    synthetic_profile = """
# Candidate Name
## General Info
Name: Alice Smith

## Executive Summary
Senior software engineer with 8 years of experience.

## Work Experience
### Senior Engineer | Tech Corp
- Built scalable services
- Led backend team
- Optimized database queries

## Academic Background
- B.Sc. Computer Science, University of Technology

## Key Qualifications & Expertise
- Python, PostgreSQL, Docker

## Personal Projects
- Open source CLI tool

## Certificates
- AWS Certified Solutions Architect
"""
    sections = parse_profile_sections(synthetic_profile)
    assert sections == [
        "personal_info",
        "summary",
        "experience",
        "education",
        "skills",
        "projects",
        "certifications",
    ]


def test_validate_profile_completeness_complete_profile():
    """Verify complete profile with required core sections passes completeness check."""
    synthetic_profile = """
# Candidate Profile
## General Information
Name: Alice Smith
## Summary
Experienced engineer.

## Work Experience
- Software Developer at ACME

## Academic Background
- B.Sc. Computer Science

## Technical Skills
- Python, FastAPI, Linux
"""
    sections = validate_profile_completeness(synthetic_profile)
    assert "experience" in sections
    assert "education" in sections
    assert "skills" in sections
    assert "projects" not in sections
    assert "certifications" not in sections


def test_validate_profile_completeness_missing_core_sections():
    """Verify missing core section (experience, education, or skills) raises ValueError."""
    incomplete_no_education = """
# Candidate Profile
## Work Experience
- Software Developer at ACME

## Technical Skills
- Python, FastAPI
"""
    with pytest.raises(ValueError, match="Missing required core sections: education"):
        validate_profile_completeness(incomplete_no_education)

    incomplete_no_experience_or_skills = """
# Candidate Profile
## Education
- B.Sc. Computer Science
"""
    with pytest.raises(ValueError, match="Missing required core sections:") as exc_info:
        validate_profile_completeness(incomplete_no_experience_or_skills)
    assert "experience" in str(exc_info.value)
    assert "skills" in str(exc_info.value)


def test_validate_profile_completeness_optional_sections_handling():
    """Verify projects and certifications are required only if present in profile headings."""
    profile_without_optionals = """
## General Information
Name: Alice Smith
## Summary
Experienced engineer.
## Professional Experience
- Senior Backend Developer

## Education
- M.Sc. Software Engineering

## Skills
- Python, SQL, Git
"""
    sections = validate_profile_completeness(profile_without_optionals)
    assert set(sections) == {
        "personal_info",
        "summary",
        "experience",
        "education",
        "skills",
    }

    profile_with_projects = """
## General Information
Name: Alice Smith
## Summary
Experienced engineer.
## Professional Experience
- Senior Backend Developer

## Education
- M.Sc. Software Engineering

## Skills
- Python, SQL, Git

## Projects
- My Open Source Project
"""
    sections_with_proj = validate_profile_completeness(profile_with_projects)
    assert set(sections_with_proj) == {
        "personal_info",
        "summary",
        "experience",
        "education",
        "skills",
        "projects",
    }


def test_crewai_evaluate_and_generate_enforce_completeness_guardrail(tmp_path):
    """Verify evaluation and generation fail immediately before LLM call on incomplete profile."""
    incomplete_profile = "## Work Experience\n- Dev\n## Skills\n- Python"
    test_profile_path = tmp_path / "profile.md"
    test_profile_path.write_text(incomplete_profile, encoding="utf-8")

    mock_vacancy = MagicMock()
    mock_vacancy.text = "Python Dev Vacancy"
    mock_vacancy.title = "Backend Engineer"
    mock_vacancy.submit_email = "jobs@example.com"
    mock_vacancy.submit_url = None

    with (
        patch("ljpa_reworked.crew_workflow.PROFILE_FILE_PATH", str(test_profile_path)),
        patch("ljpa_reworked.crew_workflow.ResumeEvaluationCrew") as mock_eval_crew,
    ):
        with pytest.raises(
            ValueError, match="Missing required core sections: education"
        ):
            crewai_evaluate_vacancy(mock_vacancy)

        mock_eval = BasicEvaluationCrewAI(summary="OK", rating=80)
        with pytest.raises(
            ValueError, match="Missing required core sections: education"
        ):
            crewai_generate_resume(mock_vacancy, mock_eval)

        mock_eval_crew.assert_not_called()


def test_validate_resume_facts_against_deterministic_present_sections():
    """Verify validate_resume_facts checks generated resume against deterministic present sections."""
    present_sections = ["experience", "education", "skills", "projects"]
    eval_model = BasicEvaluationCrewAI(
        summary="Candidate evaluation",
        rating=85,
        required_profile_sections=["experience"],  # LLM provided fewer sections
    )

    resume_missing_projects = ResumeCrewAI(
        personal_info=PersonalInfoCrewAI(
            name="Test Candidate",
            email="test@example.com",
            phone="+1 555 0199",
            address="123 Main St",
            location="Berlin",
        ),
        summary="Engineer",
        education=[
            EducationCrewAI(
                course="B.Sc. CS",
                institution="Tech Uni",
                location="Berlin",
                start_date="2016",
                end_date="2020",
            )
        ],
        experience=[
            ExperienceCrewAI(
                title="Dev",
                company="Corp",
                location="Berlin",
                start_date="2020",
                end_date="2022",
                description=["Bullet 1", "Bullet 2", "Bullet 3"],
            )
        ],
        skills=[SkillCrewAI(title="Languages", elements=["Python"])],
        projects=[],  # Projects required by deterministic list, but missing in resume
    )

    with pytest.raises(
        ValueError, match="Required profile section 'projects' is missing or empty"
    ):
        validate_resume_facts(
            resume_missing_projects, eval_model, present_sections=present_sections
        )
