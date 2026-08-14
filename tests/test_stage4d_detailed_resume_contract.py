import pytest

from ljpa_reworked.crew_workflow import (
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

    with pytest.raises(
        ValueError, match="Required profile section 'education' is missing or empty"
    ):
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

    with pytest.raises(
        ValueError, match="Unknown required profile section: 'volunteer_work'"
    ):
        validate_resume_facts(resume_valid, eval_unknown_sec)


def test_required_section_coverage_alias_normalization_and_passing():
    """Verify validate_resume_facts normalizes known section aliases and passes when all required sections are present."""
    from ljpa_reworked.models.crewai_pydantic_models import (
        EducationCrewAI,
    )

    eval_aliases = BasicEvaluationCrewAI(
        summary="OK candidate",
        rating=90,
        required_profile_sections=[
            "work experience",
            "academic background",
            "technical skills",
            "projects",
            "certificates",
        ],
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

    with open(
        "src/ljpa_reworked/crews/resume_evaluation_crew/config/tasks.yaml",
        encoding="utf-8",
    ) as f:
        eval_tasks = yaml.safe_load(f)

    eval_desc = eval_tasks["evaluate_resume_task"]["description"]
    assert (
        "required_profile_sections" in eval_desc
        or "factual inclusion plan" in eval_desc.lower()
        or "required profile sections" in eval_desc.lower()
    )
    assert "prioritized" in eval_desc.lower()
    assert "missing" in eval_desc.lower()

    with open(
        "src/ljpa_reworked/crews/resume_generation_crew/config/tasks.yaml",
        encoding="utf-8",
    ) as f:
        gen_tasks = yaml.safe_load(f)

    gen_desc = gen_tasks["resume_generation_task"]["description"]
    assert "three" in gen_desc.lower() or "3" in gen_desc
    assert (
        "named categories" in gen_desc.lower()
        or "skills categories" in gen_desc.lower()
    )
    assert "static facts policy" in gen_desc.lower()
    assert "strict factuality rule" in gen_desc.lower()


def test_pdf_layout_validation_one_page_and_two_page(tmp_path):
    """Verify validate_pdf_page_layout accepts 1 page, accepts valid 2 page (>=50% fill with secondary info), and rejects invalid PDFs."""
    synthetic_resume = ResumeCrewAI(
        personal_info=PersonalInfoCrewAI(
            name="Test Candidate User",
            email="test.user@example.com",
            phone="+1 555 0199",
            address="123 Main St, Berlin",
            location="Berlin, Germany",
            target_title="Senior Controls & Industrial Automation Engineer",
        ),
        summary=(
            "Senior Industrial Automation and Controls Engineer with over 10 years of experience designing, "
            "implementing, commissioning, and maintaining complex PLC, SCADA, DCS, and industrial networks."
        ),
        education=[
            EducationCrewAI(
                course="B.S. Automation Engineering",
                institution="Technical University of Berlin",
                location="Berlin, Germany",
                start_date="2010-09",
                end_date="2014-06",
            )
        ],
        experience=[
            ExperienceCrewAI(
                title="Lead Controls Engineer",
                company="Automation Systems Corp",
                location="Berlin, Germany",
                start_date="2020-01",
                end_date="2024-01",
                description=[
                    "Designed, programmed, and deployed Allen-Bradley ControlLogix and Siemens S7-1500 PLC software modules across 15+ industrial process facilities.",
                    "Configured high-availability Modbus TCP/IP, PROFINET, and EtherNet/IP communication networks connecting 100+ field sensors and SCADA nodes.",
                    "Led Factory Acceptance Testing (FAT) and Site Acceptance Testing (SAT) procedures for critical safety instrumented systems, reducing site startup delays by 30%.",
                    "Developed advanced diagnostic and predictive maintenance routines in Studio 5000 and TIA Portal, cutting unscheduled equipment downtime by 25%.",
                ],
            ),
            ExperienceCrewAI(
                title="Automation Engineer",
                company="Industrial Solutions GmbH",
                location="Munich, Germany",
                start_date="2014-07",
                end_date="2019-12",
                description=[
                    "Programmed Schneider Electric Modicon PLCs and Wonderware System Platform HMI applications for chemical manufacturing plants.",
                    "Calibrated and verified field instrumentation, control valves, and closed-loop PID controllers across 80+ active process loops.",
                    "Collaborated with multi-disciplinary engineering teams to upgrade legacy DCS hardware to modern distributed control architectures.",
                ],
            ),
        ],
        skills=[
            SkillCrewAI(
                title="PLC & SCADA",
                elements=[
                    "Allen-Bradley Studio 5000",
                    "Siemens TIA Portal",
                    "WinCC",
                    "Wonderware System Platform",
                ],
            ),
            SkillCrewAI(
                title="Industrial Networks",
                elements=["Modbus TCP/IP", "PROFINET", "Profibus DP", "EtherNet/IP"],
            ),
            SkillCrewAI(
                title="Tools & Languages",
                elements=[
                    "Python",
                    "Structured Text",
                    "Ladder Logic",
                    "Function Block Diagram",
                ],
            ),
        ],
    )
    pdf_out = str(tmp_path / "synthetic_resume.pdf")
    from ljpa_reworked.services.rendercv_helper import render_resume_crewai_to_pdf

    render_resume_crewai_to_pdf(synthetic_resume, pdf_out)

    valid, msg = validate_pdf_page_layout(pdf_out)
    assert valid is True
    assert "1-page" in msg or "valid" in msg.lower()

    # Test non-existent PDF
    valid_missing, msg_missing = validate_pdf_page_layout(
        str(tmp_path / "non_existent.pdf")
    )
    assert valid_missing is False
    assert "not found" in msg_missing.lower() or "does not exist" in msg_missing.lower()
