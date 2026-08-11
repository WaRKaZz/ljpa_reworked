import os
from datetime import datetime
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


def test_save_resume_successful_persistence(db_session: Session, sample_resume, sample_vacancy, tmp_path):
    """Verify save_resume renders via RenderCV helper, creates non-empty file, and stores relative filename + rendered_at."""

    def mock_render(resume_data, out_path):
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(b"%PDF-1.4 mock pdf content")
        return out_path

    with patch("ljpa_reworked.workflow.RESOURCES_DIR", str(tmp_path)), patch(
        "ljpa_reworked.workflow.render_resume_crewai_to_pdf", side_effect=mock_render
    ) as mock_helper:
        orm_resume = save_resume(sample_resume, sample_vacancy, db_session)

        mock_helper.assert_called_once()

        # Path stored must be relative filename, not absolute path
        assert not os.path.isabs(orm_resume.path)
        assert "/" not in orm_resume.path
        assert "\\" not in orm_resume.path
        assert orm_resume.path.endswith(".pdf")

        # rendered_at must be populated timestamp
        assert orm_resume.rendered_at is not None
        assert isinstance(orm_resume.rendered_at, datetime)

        # File must exist under tmp_path/resumes/<path>
        expected_file_path = tmp_path / "resumes" / orm_resume.path
        assert expected_file_path.exists()
        assert expected_file_path.stat().st_size > 0

        # DB query verification
        db_resume = db_session.query(Resume).filter(Resume.id == orm_resume.id).first()
        assert db_resume is not None
        assert db_resume.path == orm_resume.path
        assert db_resume.rendered_at == orm_resume.rendered_at


def test_save_resume_rendering_failure_leaves_no_db_row_or_file(
    db_session: Session, sample_resume, sample_vacancy, tmp_path
):
    """Verify that if render_resume_crewai_to_pdf raises an error, no DB row or leftover file is created."""
    with patch("ljpa_reworked.workflow.RESOURCES_DIR", str(tmp_path)), patch(
        "ljpa_reworked.workflow.render_resume_crewai_to_pdf",
        side_effect=RuntimeError("RenderCV failed"),
    ):
        with pytest.raises(RuntimeError, match="RenderCV failed"):
            save_resume(sample_resume, sample_vacancy, db_session)

        # No DB row
        assert db_session.query(Resume).count() == 0

        # No leftover PDF file in resumes directory
        resumes_dir = tmp_path / "resumes"
        if resumes_dir.exists():
            pdf_files = list(resumes_dir.glob("*.pdf"))
            assert len(pdf_files) == 0


def test_save_resume_empty_file_leaves_no_db_row_or_file(
    db_session: Session, sample_resume, sample_vacancy, tmp_path
):
    """Verify that if rendering produces a 0-byte file, save_resume raises RuntimeError and cleans up."""

    def mock_render_empty(resume_data, out_path):
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(b"")  # empty
        return out_path

    with patch("ljpa_reworked.workflow.RESOURCES_DIR", str(tmp_path)), patch(
        "ljpa_reworked.workflow.render_resume_crewai_to_pdf", side_effect=mock_render_empty
    ):
        with pytest.raises(RuntimeError):
            save_resume(sample_resume, sample_vacancy, db_session)

        # No DB row
        assert db_session.query(Resume).count() == 0

        # Empty file removed
        resumes_dir = tmp_path / "resumes"
        if resumes_dir.exists():
            pdf_files = list(resumes_dir.glob("*.pdf"))
            assert len(pdf_files) == 0


def test_save_resume_db_failure_cleans_up_pdf_and_reraises(
    db_session: Session, sample_resume, sample_vacancy, tmp_path
):
    """Verify that if create_resume fails after rendering a non-empty PDF, the PDF is removed and error re-raised."""

    def mock_render(resume_data, out_path):
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(b"%PDF-1.4 valid content")
        return out_path

    with patch("ljpa_reworked.workflow.RESOURCES_DIR", str(tmp_path)), patch(
        "ljpa_reworked.workflow.render_resume_crewai_to_pdf", side_effect=mock_render
    ), patch(
        "ljpa_reworked.workflow.create_resume", side_effect=RuntimeError("DB Commit Failed")
    ):
        with pytest.raises(RuntimeError, match="DB Commit Failed"):
            save_resume(sample_resume, sample_vacancy, db_session)

        # PDF file cleaned up
        resumes_dir = tmp_path / "resumes"
        if resumes_dir.exists():
            pdf_files = list(resumes_dir.glob("*.pdf"))
            assert len(pdf_files) == 0


def test_legacy_resume_generator_import_removed():
    """Verify ResumeGenerator is not imported in ljpa_reworked.workflow."""
    import ljpa_reworked.workflow as wf

    assert not hasattr(wf, "ResumeGenerator")
