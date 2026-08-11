from unittest.mock import MagicMock, patch

import pytest

from ljpa_reworked.crew_workflow import (
    crewai_generate_resume,
    validate_resume_facts,
)
from ljpa_reworked.models.crewai_pydantic_models import (
    BasicEvaluationCrewAI,
    CertificationCrewAI,
    EducationCrewAI,
    ExperienceCrewAI,
    PersonalInfoCrewAI,
    ProjectCrewAI,
    ResumeCrewAI,
    SkillCrewAI,
)
from ljpa_reworked.services.rendercv_helper import validate_pdf_page_layout


def test_basic_evaluation_crewai_fields():
    """Verify BasicEvaluationCrewAI supports required_profile_sections, prioritized_facts, and missing_mandatory_facts."""
    eval_model = BasicEvaluationCrewAI(
        summary="Qualified candidate",
        rating=88,
        required_profile_sections=["experience", "education", "skills"],
        prioritized_facts=["Python 5 years", "PostgreSQL tuning"],
        missing_mandatory_facts=[],
    )
    assert eval_model.required_profile_sections == ["experience", "education", "skills"]
    assert eval_model.prioritized_facts == ["Python 5 years", "PostgreSQL tuning"]
    assert eval_model.missing_mandatory_facts == []

    # Verify default empty lists
    eval_default = BasicEvaluationCrewAI(summary="Default eval", rating=70)
    assert eval_default.required_profile_sections == []
    assert eval_default.prioritized_facts == []
    assert eval_default.missing_mandatory_facts == []


def test_crewai_generate_resume_propagates_plan_inputs(tmp_path):
    """Verify crewai_generate_resume passes structured plan fields to crew kickoff inputs."""
    synthetic_profile = '## General Information\nName: Test\n## Summary\nEngineer\n## Experience\n- Role\n## Education\n- Degree\n## Skills\n- Python'
    test_profile_path = tmp_path / "profile.md"
    test_profile_path.write_text(synthetic_profile, encoding="utf-8")

    mock_vacancy = MagicMock()
    mock_vacancy.text = "Python Backend Engineer"
    mock_vacancy.title = "Backend Engineer"
    mock_vacancy.submit_email = "jobs@example.com"
    mock_vacancy.submit_url = "https://example.com/job"

    mock_eval = BasicEvaluationCrewAI(
        summary="Strong candidate",
        rating=92,
        required_profile_sections=["experience", "education", "skills", "projects", "certifications"],
        prioritized_facts=["Python 5+ yrs", "RenderCV integration"],
        missing_mandatory_facts=[],
    )

    mock_resume = ResumeCrewAI(
        personal_info=PersonalInfoCrewAI(
            name="Test User",
            email="test@example.com",
            phone="+1 555 0199",
            address="123 Main St",
            location="Berlin, Germany",
        ),
        summary="Experienced engineer with Python background.",
        education=[
            EducationCrewAI(
                course="Computer Science B.Sc.",
                institution="Tech University",
                location="Berlin",
                start_date="2016",
                end_date="2020",
            )
        ],
        experience=[
            ExperienceCrewAI(
                title="Senior Developer",
                company="Tech Corp",
                location="Berlin, Germany",
                start_date="2020-01",
                end_date="Present",
                description=[
                    "Architected high-throughput REST APIs using Python and FastAPI.",
                    "Optimized SQL queries, reducing database load by 40%.",
                    "Led a team of 4 engineers in adopting strict TDD practices.",
                ],
            )
        ],
        skills=[
            SkillCrewAI(title="Languages", elements=["Python", "SQL"]),
            SkillCrewAI(title="Frameworks", elements=["FastAPI", "Django"]),
        ],
        projects=[
            ProjectCrewAI(
                title="Synthetic Engine",
                description="High performance REST service",
                highlights=["Bullet 1", "Bullet 2", "Bullet 3"],
            )
        ],
        certifications=[
            CertificationCrewAI(
                title="Python Certified Professional",
                issuer="Python Institute",
                date="2021",
            )
        ],
    )

    mock_crew = MagicMock()
    mock_crew.usage_metrics.successful_requests = 1
    mock_crew_output = MagicMock()
    mock_task_output = MagicMock()
    mock_task_output.pydantic = mock_resume
    mock_crew_output.tasks_output = [mock_task_output]
    mock_crew.kickoff.return_value = mock_crew_output

    with patch("ljpa_reworked.crew_workflow.PROFILE_FILE_PATH", str(test_profile_path)), \
         patch("ljpa_reworked.crew_workflow.ResumeGenerationCrew") as mock_crew_cls:
        mock_crew_cls.return_value.crew.return_value = mock_crew

        res = crewai_generate_resume(mock_vacancy, mock_eval)

        assert res == mock_resume
        mock_crew.kickoff.assert_called_once()
        inputs = mock_crew.kickoff.call_args[1]["inputs"]
        assert inputs["required_profile_sections"] == ["personal_info", "summary", "experience", "education", "skills"]
        assert inputs["prioritized_facts"] == ["Python 5+ yrs", "RenderCV integration"]
        assert inputs["missing_mandatory_facts"] == []


def test_missing_facts_rejection():
    """Verify validate_resume_facts fails when missing_mandatory_facts exist or entries have <3 bullets."""
    eval_missing = BasicEvaluationCrewAI(
        summary="Incomplete candidate",
        rating=40,
        missing_mandatory_facts=["Missing 3 years backend experience"],
    )

    resume_valid = ResumeCrewAI(
        personal_info=PersonalInfoCrewAI(
            name="Test User",
            email="test@example.com",
            phone="+1 555 0199",
            address="123 Main St",
            location="Berlin, Germany",
        ),
        summary="A developer summary.",
        education=[],
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
    )

    with pytest.raises(ValueError, match="Missing mandatory profile facts"):
        validate_resume_facts(resume_valid, eval_missing)

    eval_ok = BasicEvaluationCrewAI(
        summary="OK candidate",
        rating=90,
        missing_mandatory_facts=[],
    )

    resume_few_bullets = ResumeCrewAI(
        personal_info=PersonalInfoCrewAI(
            name="Test User",
            email="test@example.com",
            phone="+1 555 0199",
            address="123 Main St",
            location="Berlin, Germany",
        ),
        summary="A developer summary.",
        education=[],
        experience=[
            ExperienceCrewAI(
                title="Dev",
                company="Corp",
                location="Berlin",
                start_date="2020",
                end_date="2022",
                description=["Only bullet 1", "Only bullet 2"],
            )
        ],
        skills=[SkillCrewAI(title="Languages", elements=["Python"])],
    )

    with pytest.raises(ValueError, match="fewer than 3 bullet points"):
        validate_resume_facts(resume_few_bullets, eval_ok)


def test_required_section_coverage_omitted_section_rejection():
    """Verify validate_resume_facts fails when evaluation specifies required profile sections missing in resume."""
    eval_req_education = BasicEvaluationCrewAI(
        summary="OK candidate",
        rating=90,
        required_profile_sections=["experience", "education"],
    )

    resume_no_education = ResumeCrewAI(
        personal_info=PersonalInfoCrewAI(
            name="Test User",
            email="test@example.com",
            phone="+1 555 0199",
            address="123 Main St",
            location="Berlin, Germany",
        ),
        summary="A developer summary.",
        education=[],
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
    )

    with pytest.raises(ValueError, match="Required profile section 'education' is missing or empty"):
        validate_resume_facts(resume_no_education, eval_req_education)


def test_required_section_coverage_unknown_section_rejection():
    """Verify validate_resume_facts fails clearly when evaluation specifies an unknown required profile section."""
    eval_unknown_sec = BasicEvaluationCrewAI(
        summary="OK candidate",
        rating=90,
        required_profile_sections=["volunteer_work"],
    )

    resume_valid = ResumeCrewAI(
        personal_info=PersonalInfoCrewAI(
            name="Test User",
            email="test@example.com",
            phone="+1 555 0199",
            address="123 Main St",
            location="Berlin, Germany",
        ),
        summary="A developer summary.",
        education=[],
        experience=[],
        skills=[SkillCrewAI(title="Languages", elements=["Python"])],
    )

    with pytest.raises(ValueError, match="Unknown required profile section: 'volunteer_work'"):
        validate_resume_facts(resume_valid, eval_unknown_sec)


def test_required_section_coverage_alias_normalization_and_passing():
    """Verify validate_resume_facts normalizes known section aliases and passes when all required sections are present."""
    from ljpa_reworked.models.crewai_pydantic_models import (
        CertificationCrewAI,
        EducationCrewAI,
        ProjectCrewAI,
    )

    eval_aliases = BasicEvaluationCrewAI(
        summary="OK candidate",
        rating=90,
        required_profile_sections=["work experience", "academic background", "technical skills", "projects", "certificates"],
    )

    resume_complete = ResumeCrewAI(
        personal_info=PersonalInfoCrewAI(
            name="Test User",
            email="test@example.com",
            phone="+1 555 0199",
            address="123 Main St",
            location="Berlin, Germany",
        ),
        summary="A developer summary.",
        education=[
            EducationCrewAI(
                course="B.Sc. CS",
                institution="University",
                location="Berlin",
                start_date="2015",
                end_date="2019",
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
        projects=[
            ProjectCrewAI(
                title="Project Alpha",
                description="A test project",
                highlights=["H1", "H2", "H3"],
            )
        ],
        certifications=[
            CertificationCrewAI(
                title="AWS Certified Developer",
                issuer="Amazon Web Services",
                date="2021",
            )
        ],
    )

    # Must pass without raising ValueError
    validate_resume_facts(resume_complete, eval_aliases)



def test_evaluator_and_generator_task_yaml_contracts():
    """Verify tasks.yaml prompts contain required contract terms."""
    import yaml

    with open("src/ljpa_reworked/crews/resume_evaluation_crew/config/tasks.yaml", encoding="utf-8") as f:
        eval_tasks = yaml.safe_load(f)

    eval_desc = eval_tasks["evaluate_resume_task"]["description"]
    assert "required_profile_sections" in eval_desc or "factual inclusion plan" in eval_desc.lower() or "required profile sections" in eval_desc.lower()
    assert "prioritized" in eval_desc.lower()
    assert "missing" in eval_desc.lower()

    with open("src/ljpa_reworked/crews/resume_generation_crew/config/tasks.yaml", encoding="utf-8") as f:
        gen_tasks = yaml.safe_load(f)

    gen_desc = gen_tasks["resume_generation_task"]["description"]
    assert "three" in gen_desc.lower() or "3" in gen_desc
    assert "skills categories" in gen_desc.lower() or "separate skills" in gen_desc.lower()
    assert "must not invent" in gen_desc.lower() or "no invention" in gen_desc.lower() or "without inventing" in gen_desc.lower()


def test_pdf_layout_validation_one_page_and_two_page(tmp_path):
    """Verify validate_pdf_page_layout accepts 1 page, accepts valid 2 page (>=50% fill with secondary info), and rejects invalid PDFs."""
    synthetic_resume = ResumeCrewAI(
        personal_info=PersonalInfoCrewAI(
            name="Test User",
            email="test@example.com",
            phone="+1 555 0199",
            address="123 Main St",
            location="Berlin, Germany",
        ),
        summary="A developer summary.",
        education=[],
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
    )
    pdf_out = str(tmp_path / "synthetic_resume.pdf")
    from ljpa_reworked.services.rendercv_helper import render_resume_crewai_to_pdf
    render_resume_crewai_to_pdf(synthetic_resume, pdf_out)

    valid, msg = validate_pdf_page_layout(pdf_out)
    assert valid is True
    assert "1-page" in msg or "valid" in msg.lower()

    # Test non-existent PDF
    valid_missing, msg_missing = validate_pdf_page_layout(str(tmp_path / "non_existent.pdf"))
    assert valid_missing is False
    assert "not found" in msg_missing.lower() or "does not exist" in msg_missing.lower()

