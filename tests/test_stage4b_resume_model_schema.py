from datetime import datetime
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ljpa_reworked.database import init_db
from ljpa_reworked.models.crewai_pydantic_models import (
    CertificationCrewAI,
    EducationCrewAI,
    ExperienceCrewAI,
    PersonalInfoCrewAI,
    ProjectCrewAI,
    ResumeCrewAI,
    SkillCrewAI,
    VisaStatus,
)
from ljpa_reworked.models.database_models import DataSource, Vacancy
from ljpa_reworked.models.enums import VacancyStatus
from ljpa_reworked.operations import (
    confirm_email_application_submitted,
    create_email,
    create_resume,
    get_resume_by_id,
    transition_vacancy_status,
)
from ljpa_reworked.workflow import send_email


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    session = Session(bind=engine)
    try:
        yield session
    finally:
        session.close()


def test_pydantic_resume_new_ats_fields():
    """Verify ATS fields on PersonalInfoCrewAI, ProjectCrewAI, and CertificationCrewAI."""
    # PersonalInfo requires location, accepts optional linkedin_url
    info = PersonalInfoCrewAI(
        name="Jane Developer",
        email="jane@example.com",
        phone="+1-555-0199",
        address="123 Code Street",
        location="Berlin, Germany",
        linkedin_url="https://linkedin.com/in/janedev",
    )
    assert info.location == "Berlin, Germany"
    assert info.linkedin_url == "https://linkedin.com/in/janedev"

    # Missing location should raise ValidationError
    with pytest.raises(ValidationError):
        PersonalInfoCrewAI(
            name="Jane Developer",
            email="jane@example.com",
            phone="+1-555-0199",
            address="123 Code Street",
        )

    # Project with optional ATS fields
    proj = ProjectCrewAI(
        title="Open Source Parser",
        description="Fast parser written in Python",
        url="https://github.com/example/parser",
        start_date="2023-01",
        end_date="2023-06",
        highlights=["Implemented AST parsing", "Achieved 99% coverage"],
    )
    assert proj.url == "https://github.com/example/parser"
    assert proj.start_date == "2023-01"
    assert proj.end_date == "2023-06"
    assert len(proj.highlights) == 2

    # Certification with optional ATS fields
    cert = CertificationCrewAI(
        title="AWS Solutions Architect",
        issuer="Amazon Web Services",
        date="2024-05",
        url="https://aws.amazon.com/cert/123",
    )
    assert cert.issuer == "Amazon Web Services"
    assert cert.date == "2024-05"
    assert cert.url == "https://aws.amazon.com/cert/123"

    # Full ResumeCrewAI instantiation
    resume_data = ResumeCrewAI(
        personal_info=info,
        summary="A summary string...",
        education=[
            EducationCrewAI(
                course="B.S. CS",
                institution="Tech Uni",
                location="Berlin",
                start_date="2018",
                end_date="2022",
            )
        ],
        experience=[
            ExperienceCrewAI(
                title="Backend Dev",
                company="Startup Inc",
                location="Remote",
                start_date="2022",
                end_date="Present",
                description=["Built REST APIs"],
            )
        ],
        skills=[SkillCrewAI(title="Languages", elements=["Python", "Go"])],
        projects=[proj],
        certifications=[cert],
    )
    assert resume_data.personal_info.location == "Berlin, Germany"
    assert resume_data.projects[0].highlights == ["Implemented AST parsing", "Achieved 99% coverage"]
    assert resume_data.certifications[0].issuer == "Amazon Web Services"


def test_resume_orm_json_persistence_and_nullable_columns(db_session: Session):
    """Verify new fields round-trip into SQLite JSON columns and nullable rendered_at/applied_at exist."""
    vacancy = Vacancy(
        title="Senior Python Developer",
        text="Looking for a senior developer...",
        submit_email="recruiter@example.com",
        source=DataSource.linkedin,
        visa_status=VisaStatus.not_required,
    )
    db_session.add(vacancy)
    db_session.commit()

    # Verify initial nullable columns on fresh schema
    assert hasattr(vacancy, "applied_at")
    assert vacancy.applied_at is None

    resume_pydantic = ResumeCrewAI(
        personal_info=PersonalInfoCrewAI(
            name="Alice Smith",
            email="alice@example.com",
            phone="123456",
            address="789 Pine Rd",
            location="London, UK",
            linkedin_url="https://linkedin.com/in/alicesmith",
        ),
        summary="Experienced Python engineer.",
        education=[
            EducationCrewAI(
                course="M.S. Software Engineering",
                institution="Oxford",
                location="Oxford, UK",
                start_date="2017",
                end_date="2018",
            )
        ],
        experience=[
            ExperienceCrewAI(
                title="Lead Developer",
                company="FinTech Ltd",
                location="London, UK",
                start_date="2018",
                end_date="2024",
                description=["Led team of 5"],
            )
        ],
        skills=[SkillCrewAI(title="Languages", elements=["Python", "SQL"])],
        projects=[
            ProjectCrewAI(
                title="High Speed Engine",
                description="Engine project",
                url="https://github.com/alice/engine",
                start_date="2021",
                end_date="2022",
                highlights=["Reduced latency by 40%"],
            )
        ],
        certifications=[
            CertificationCrewAI(
                title="CKAD",
                issuer="CNCF",
                date="2023-01",
                url="https://cncf.io/cert/ckad",
            )
        ],
    )

    now = datetime.utcnow()
    resume_orm = create_resume(
        db=db_session,
        vacancy_id=vacancy.id,
        resume_data=resume_pydantic,
        path="alice_resume.pdf",
        rendered_at=now,
    )

    assert hasattr(resume_orm, "rendered_at")
    assert resume_orm.rendered_at == now

    # Round trip inspection
    fetched = get_resume_by_id(db_session, resume_orm.id)
    assert fetched is not None
    assert fetched.personal_info["location"] == "London, UK"
    assert fetched.personal_info["linkedin_url"] == "https://linkedin.com/in/alicesmith"
    assert fetched.projects[0]["url"] == "https://github.com/alice/engine"
    assert fetched.projects[0]["highlights"] == ["Reduced latency by 40%"]
    assert fetched.certifications[0]["issuer"] == "CNCF"
    assert fetched.certifications[0]["url"] == "https://cncf.io/cert/ckad"


def test_ordinary_transition_does_not_set_applied_at(db_session: Session):
    """Ordinary transition_vacancy_status to applied must not silently set applied_at."""
    vacancy = Vacancy(
        title="DevOps Engineer",
        text="DevOps role...",
        submit_email="jobs@devops.com",
        source=DataSource.linkedin,
        visa_status=VisaStatus.not_required,
    )
    db_session.add(vacancy)
    db_session.commit()

    assert vacancy.applied_at is None
    transition_vacancy_status(db_session, vacancy.id, VacancyStatus.applied)
    db_session.refresh(vacancy)
    assert vacancy.status == VacancyStatus.applied
    assert vacancy.applied_at is None


def test_confirmed_email_submission_sets_applied_at_only_on_success(db_session: Session, tmp_path):
    """Confirmed email submission sets applied_at after successful send & transition, leaves unset on failure."""
    vacancy = Vacancy(
        title="Backend Engineer",
        text="Backend engineering role...",
        submit_email="hr@techcorp.com",
        source=DataSource.linkedin,
        visa_status=VisaStatus.not_required,
    )
    db_session.add(vacancy)
    db_session.commit()

    # Case 1: Send email fails -> applied_at remains None, status not applied
    email_data = create_email(
        db=db_session,
        vacancy_id=vacancy.id,
        email_data=type("EmailData", (), {"subject": "Application", "body": "Hello"})(),
        recipient="hr@techcorp.com",
        resume_path="dummy_resume.pdf",
    )

    resumes_dir = tmp_path / "resumes"
    resumes_dir.mkdir(parents=True, exist_ok=True)
    dummy_resume = resumes_dir / "dummy_resume.pdf"
    dummy_resume.write_text("pdf content")

    with patch("ljpa_reworked.workflow.RESOURCES_DIR", str(tmp_path)), \
         patch("ljpa_reworked.workflow.SMTPClient") as mock_smtp:
        mock_smtp.return_value.__enter__.return_value.send_email.side_effect = RuntimeError("SMTP connection failed")
        with pytest.raises(RuntimeError):
            send_email(email_data)

    db_session.refresh(vacancy)
    assert vacancy.applied_at is None
    assert vacancy.status == VacancyStatus.created

    # Case 2: Send email succeeds -> confirmed transition stamps applied_at
    with patch("ljpa_reworked.workflow.RESOURCES_DIR", str(tmp_path)), \
         patch("ljpa_reworked.workflow.shutil.copy"), \
         patch("ljpa_reworked.workflow.SMTPClient") as mock_smtp:
        mock_smtp.return_value.__enter__.return_value.send_email.return_value = None
        send_email(email_data)
        confirm_email_application_submitted(db_session, vacancy.id)

    db_session.refresh(vacancy)
    assert vacancy.status == VacancyStatus.applied
    assert vacancy.applied_at is not None
    assert isinstance(vacancy.applied_at, datetime)
