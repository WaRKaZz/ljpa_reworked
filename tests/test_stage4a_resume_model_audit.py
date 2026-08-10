import pytest
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
from ljpa_reworked.models.database_models import DataSource, Email, Vacancy
from ljpa_reworked.models.enums import VacancyStatus
from ljpa_reworked.operations.resume_ops import (
    create_resume,
    get_resume_by_id,
    get_resume_by_vacancy,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    session = Session(bind=engine)
    try:
        yield session
    finally:
        session.close()


def test_resume_crewai_model_instantiation():
    resume_data = ResumeCrewAI(
        personal_info=PersonalInfoCrewAI(
            name="Test Candidate",
            email="candidate@example.com",
            phone="+1234567890",
            address="123 Test St, Test City",
        ),
        summary="Experienced Software Engineer with strong Python skills.",
        education=[
            EducationCrewAI(
                course="B.S. Computer Science",
                institution="Test University",
                location="Test City",
                start_date="2016",
                end_date="2020",
            )
        ],
        experience=[
            ExperienceCrewAI(
                title="Senior Developer",
                company="Tech Co",
                location="Remote",
                start_date="2020",
                end_date="Present",
                description=["Built backend services", "Optimized database queries"],
            )
        ],
        skills=[
            SkillCrewAI(title="Languages", elements=["Python", "SQL", "Bash"])
        ],
        projects=[
            ProjectCrewAI(
                title="Open Source Tool",
                description="CLI utility for data processing",
            )
        ],
        certifications=[
            CertificationCrewAI(title="AWS Certified Developer")
        ],
    )

    assert resume_data.personal_info.name == "Test Candidate"
    assert resume_data.summary.startswith("Experienced Software Engineer")
    assert len(resume_data.education) == 1
    assert len(resume_data.experience) == 1
    assert len(resume_data.skills) == 1
    assert len(resume_data.projects) == 1
    assert len(resume_data.certifications) == 1


def test_create_and_query_resume_orm(db_session: Session):
    vacancy = Vacancy(
        title="Python Engineer",
        text="Looking for a Python engineer...",
        submit_email="jobs@example.com",
        source=DataSource.linkedin,
        visa_status=VisaStatus.not_required,
    )
    db_session.add(vacancy)
    db_session.commit()

    resume_pydantic = ResumeCrewAI(
        personal_info=PersonalInfoCrewAI(
            name="John Doe",
            email="john@example.com",
            phone="+111222333",
            address="456 Main St",
        ),
        summary="Python developer with experience in microservices.",
        education=[
            EducationCrewAI(
                course="Computer Science",
                institution="State University",
                location="State City",
                start_date="2015",
                end_date="2019",
            )
        ],
        experience=[
            ExperienceCrewAI(
                title="Software Engineer",
                company="Dev Inc",
                location="City",
                start_date="2019",
                end_date="2023",
                description=["Developed APIs"],
            )
        ],
        skills=[SkillCrewAI(title="Backend", elements=["Python", "FastAPI"])],
    )

    resume_orm = create_resume(
        db=db_session,
        vacancy_id=vacancy.id,
        resume_data=resume_pydantic,
        path="test_resume.pdf",
    )

    assert resume_orm.id is not None
    assert resume_orm.vacancy_id == vacancy.id
    assert resume_orm.fullname == "John Doe"
    assert resume_orm.email == "john@example.com"
    assert resume_orm.path == "test_resume.pdf"

    # Query tests
    fetched = get_resume_by_vacancy(db_session, vacancy.id)
    assert fetched is not None
    assert fetched.id == resume_orm.id

    fetched_by_id = get_resume_by_id(db_session, resume_orm.id)
    assert fetched_by_id is not None
    assert fetched_by_id.fullname == "John Doe"

    # Check to_dict() export
    data_dict = fetched.to_dict()
    assert data_dict["fullname"] == "John Doe"
    assert data_dict["vacancy_id"] == vacancy.id
    assert isinstance(data_dict["personal_info"], dict)
    assert isinstance(data_dict["education"], list)
    assert isinstance(data_dict["experience"], list)


def test_vacancystatus_has_no_sent_value():
    """Verify that VacancyStatus enum has no 'sent' member and uses 'applied' for submitted state."""
    assert not hasattr(VacancyStatus, "sent")
    assert "sent" not in [status.value for status in VacancyStatus]
    assert VacancyStatus.applied.value == "applied"


def test_vacancy_model_has_no_updated_at_column():
    """Verify that Vacancy SQLAlchemy model has no updated_at column."""
    assert not hasattr(Vacancy, "updated_at")
    assert "updated_at" not in [column.name for column in Vacancy.__table__.columns]


def test_email_created_at_is_row_creation_time():
    """Verify that Email model has created_at row creation time but no sent_at timestamp."""
    assert hasattr(Email, "created_at")
    assert not hasattr(Email, "sent_at")
    assert "sent_at" not in [column.name for column in Email.__table__.columns]


def test_languages_and_optional_links_audit_facts():
    """Verify current representation of languages in skills and partial gaps in optional links."""
    # Languages are representable via SkillCrewAI
    lang_skill = SkillCrewAI(
        title="Languages", elements=["English (Native)", "Spanish (B2)"]
    )
    assert lang_skill.title == "Languages"
    assert "English (Native)" in lang_skill.elements

    # Verify optional link field gaps on current Pydantic models
    p_info = PersonalInfoCrewAI(
        name="Candidate",
        email="c@example.com",
        phone="123",
        address="City",
    )
    assert not hasattr(p_info, "linkedin_url")

    proj = ProjectCrewAI(title="Project", description="Desc")
    assert not hasattr(proj, "url")

    cert = CertificationCrewAI(title="Cert")
    assert not hasattr(cert, "url")
    assert not hasattr(cert, "issuer")


def test_sent_evidence_sources_audit_facts(db_session: Session):
    """Verify sent evidence facts and Stage 4E metadata requirements:
    1. Email.sent is not set by main send path (defaults to False).
    2. TelegramStatus.sent records vacancy notification, not resume sent.
    3. Only VacancyStatus.applied indicates completed application submission.
    4. Vacancy has no submission timestamp, so Stage 4E requires explicit timestamp addition.
    """
    from ljpa_reworked.models.database_models import TelegramStatus

    vacancy = Vacancy(
        title="Python Engineer",
        text="Looking for a Python engineer...",
        submit_email="jobs@example.com",
        source=DataSource.linkedin,
        visa_status=VisaStatus.not_required,
    )
    db_session.add(vacancy)
    db_session.commit()

    # Email.sent exists but defaults to False and is never set to True by send_email() in main workflow
    email = Email(subject="Test", recipient="test@example.com", vacancy_id=vacancy.id)
    db_session.add(email)
    db_session.commit()
    db_session.refresh(email)
    assert email.sent is False

    # TelegramStatus.sent exists for recording Telegram vacancy notification posts
    tg = TelegramStatus(vacancy_id=vacancy.id, sent=True)
    db_session.add(tg)
    db_session.commit()
    db_session.refresh(tg)
    assert tg.sent is True

    # VacancyStatus.applied is the sole status representing completed application submission
    assert VacancyStatus.applied in VacancyStatus
    assert VacancyStatus.applied.value == "applied"

    # Vacancy lacks updated_at or applied_at timestamp for Stage 4E age tracking
    assert not hasattr(Vacancy, "updated_at")
    assert not hasattr(Vacancy, "applied_at")
