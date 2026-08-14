from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ljpa_reworked.database import init_db
from ljpa_reworked.models.crewai_pydantic_models import (
    EducationCrewAI,
    ExperienceCrewAI,
    PersonalInfoCrewAI,
    ResumeCrewAI,
    SkillCrewAI,
    VisaStatus,
)
from ljpa_reworked.models.database_models import DataSource, Resume, Vacancy
from ljpa_reworked.workflow import save_resume


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    session = Session(bind=engine)
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def sample_resume():
    return ResumeCrewAI(
        personal_info=PersonalInfoCrewAI(
            name="Alice Test",
            email="alice@example.com",
            phone="+1 555 0199",
            address="123 Main St",
            location="Berlin, Germany",
            linkedin_url="https://linkedin.com/in/alicetest",
        ),
        summary="Test summary",
        education=[
            EducationCrewAI(
                course="B.Sc. CS",
                institution="Tech Uni",
                location="Berlin, Germany",
                start_date="2018-09",
                end_date="2022-06",
            )
        ],
        experience=[
            ExperienceCrewAI(
                title="Software Engineer",
                company="Dev Corp",
                location="Berlin, Germany",
                start_date="2022-07",
                end_date="Present",
                description=["Developed Python applications"],
            )
        ],
        skills=[SkillCrewAI(title="Languages", elements=["Python", "SQL"])],
        projects=[],
        certifications=[],
    )


@pytest.fixture
def sample_vacancy(db_session: Session):
    vacancy = Vacancy(
        title="Python Engineer",
        text="Looking for a Python engineer",
        submit_email="jobs@example.com",
        source=DataSource.linkedin,
        visa_status=VisaStatus.not_required,
    )
    db_session.add(vacancy)
    db_session.commit()
    return vacancy


def test_save_resume_stores_structured_data_only(
    db_session: Session, sample_resume, sample_vacancy
):
    """Verify save_resume stores structured data only, with path and rendered_at set to None."""
    orm_resume = save_resume(sample_resume, sample_vacancy, db_session)

    # Path and rendered_at must be None
    assert orm_resume.path is None
    assert orm_resume.rendered_at is None
    assert orm_resume.vacancy_id == sample_vacancy.id
    assert orm_resume.fullname == sample_resume.personal_info.name
    assert orm_resume.email == sample_resume.personal_info.email
    assert orm_resume.summary == sample_resume.summary

    # DB query verification
    db_resume = db_session.query(Resume).filter(Resume.id == orm_resume.id).first()
    assert db_resume is not None
    assert db_resume.path is None
    assert db_resume.rendered_at is None
    assert db_resume.vacancy_id == sample_vacancy.id


def test_save_resume_deletes_supplied_temp_pdf(
    db_session: Session, sample_resume, sample_vacancy, tmp_path
):
    """Verify save_resume removes supplied temp_pdf_path if it exists."""
    temp_pdf = tmp_path / "temp.pdf"
    temp_pdf.write_bytes(b"%PDF-1.4 mock content")

    save_resume(
        sample_resume,
        sample_vacancy,
        db_session,
        temp_pdf_path=str(temp_pdf),
    )

    assert not temp_pdf.exists()


def test_save_resume_create_resume_failure_propagation(
    db_session: Session, sample_resume, sample_vacancy, tmp_path
):
    """Verify create_resume failure propagates and supplied temp_pdf_path is deleted."""
    temp_pdf = tmp_path / "temp_fail.pdf"
    temp_pdf.write_bytes(b"%PDF-1.4 mock content")

    with patch(
        "ljpa_reworked.workflow.create_resume",
        side_effect=RuntimeError("DB Commit Failed"),
    ):
        with pytest.raises(RuntimeError, match="DB Commit Failed"):
            save_resume(
                sample_resume,
                sample_vacancy,
                db_session,
                temp_pdf_path=str(temp_pdf),
            )

    assert not temp_pdf.exists()


def test_legacy_resume_generator_import_removed():
    """Verify ResumeGenerator is not imported in ljpa_reworked.workflow."""
    import ljpa_reworked.workflow as wf

    assert not hasattr(wf, "ResumeGenerator")
