from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ljpa_reworked.database import init_db
from ljpa_reworked.models.database_models import DataSource, Resume, Vacancy, VisaStatus
from ljpa_reworked.models.enums import VacancyStatus
from ljpa_reworked.services.resume_cleanup import cleanup_resume_pdfs


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    session = Session(bind=engine)
    try:
        yield session
    finally:
        session.close()


def test_cleanup_removes_unsubmitted_vacancy_resume_pdf(db_session: Session, tmp_path):
    resumes_dir = tmp_path / "resumes"
    resumes_dir.mkdir(parents=True, exist_ok=True)
    pdf_file = resumes_dir / "unsubmitted.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 dummy content")

    vacancy = Vacancy(
        title="Unsubmitted Job",
        text="Sample text",
        submit_email="test@example.com",
        source=DataSource.linkedin,
        visa_status=VisaStatus.not_required,
        status=VacancyStatus.created,
    )
    db_session.add(vacancy)
    db_session.commit()

    resume = Resume(
        fullname="John Doe",
        email="john@example.com",
        summary="Summary",
        path="unsubmitted.pdf",
        vacancy_id=vacancy.id,
    )
    db_session.add(resume)
    db_session.commit()

    now = datetime(2026, 8, 11, 12, 0, 0)
    result = cleanup_resume_pdfs(db_session, resumes_dir, now=now)

    assert result == {"removed": 1, "skipped": 0}
    assert not pdf_file.exists(), "PDF file should have been deleted"

    # Verify DB rows are intact
    assert db_session.query(Vacancy).filter_by(id=vacancy.id).first() is not None
    assert db_session.query(Resume).filter_by(id=resume.id).first() is not None


def test_cleanup_removes_stale_applied_vacancy_resume_pdf(
    db_session: Session, tmp_path
):
    resumes_dir = tmp_path / "resumes"
    resumes_dir.mkdir(parents=True, exist_ok=True)
    pdf_file = resumes_dir / "stale_applied.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 dummy content")

    now = datetime(2026, 8, 11, 12, 0, 0)
    stale_date = now - timedelta(days=65)

    vacancy = Vacancy(
        title="Stale Applied Job",
        text="Sample text",
        submit_email="test@example.com",
        source=DataSource.linkedin,
        visa_status=VisaStatus.not_required,
        status=VacancyStatus.submitted_via_all,
        applied_at=stale_date,
    )
    db_session.add(vacancy)
    db_session.commit()

    resume = Resume(
        fullname="John Doe",
        email="john@example.com",
        summary="Summary",
        path="stale_applied.pdf",
        vacancy_id=vacancy.id,
    )
    db_session.add(resume)
    db_session.commit()

    result = cleanup_resume_pdfs(db_session, resumes_dir, now=now)

    assert result == {"removed": 1, "skipped": 0}
    assert not pdf_file.exists(), "Stale applied PDF should have been deleted"
    assert db_session.query(Vacancy).filter_by(id=vacancy.id).first() is not None
    assert db_session.query(Resume).filter_by(id=resume.id).first() is not None


def test_cleanup_retains_recent_applied_vacancy_resume_pdf(
    db_session: Session, tmp_path
):
    resumes_dir = tmp_path / "resumes"
    resumes_dir.mkdir(parents=True, exist_ok=True)
    pdf_file = resumes_dir / "recent_applied.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 dummy content")

    now = datetime(2026, 8, 11, 12, 0, 0)
    recent_date = now - timedelta(days=10)

    vacancy = Vacancy(
        title="Recent Applied Job",
        text="Sample text",
        submit_email="test@example.com",
        source=DataSource.linkedin,
        visa_status=VisaStatus.not_required,
        status=VacancyStatus.submitted_via_all,
        applied_at=recent_date,
    )
    db_session.add(vacancy)
    db_session.commit()

    resume = Resume(
        fullname="John Doe",
        email="john@example.com",
        summary="Summary",
        path="recent_applied.pdf",
        vacancy_id=vacancy.id,
    )
    db_session.add(resume)
    db_session.commit()

    result = cleanup_resume_pdfs(db_session, resumes_dir, now=now)

    assert result == {"removed": 0, "skipped": 1}
    assert pdf_file.exists(), "Recent applied PDF must be retained"


def test_cleanup_handles_missing_file_as_safe_skip(db_session: Session, tmp_path):
    resumes_dir = tmp_path / "resumes"
    resumes_dir.mkdir(parents=True, exist_ok=True)

    vacancy = Vacancy(
        title="Job with missing file",
        text="Sample text",
        submit_email="test@example.com",
        source=DataSource.linkedin,
        visa_status=VisaStatus.not_required,
        status=VacancyStatus.created,
    )
    db_session.add(vacancy)
    db_session.commit()

    resume = Resume(
        fullname="John Doe",
        email="john@example.com",
        summary="Summary",
        path="missing_file.pdf",
        vacancy_id=vacancy.id,
    )
    db_session.add(resume)
    db_session.commit()

    result = cleanup_resume_pdfs(db_session, resumes_dir)

    assert result == {"removed": 0, "skipped": 1}


def test_cleanup_rejects_non_pdf_path(db_session: Session, tmp_path):
    resumes_dir = tmp_path / "resumes"
    resumes_dir.mkdir(parents=True, exist_ok=True)
    txt_file = resumes_dir / "notes.txt"
    txt_file.write_text("important notes")

    vacancy = Vacancy(
        title="Job with non-pdf resume path",
        text="Sample text",
        submit_email="test@example.com",
        source=DataSource.linkedin,
        visa_status=VisaStatus.not_required,
        status=VacancyStatus.created,
    )
    db_session.add(vacancy)
    db_session.commit()

    resume = Resume(
        fullname="John Doe",
        email="john@example.com",
        summary="Summary",
        path="notes.txt",
        vacancy_id=vacancy.id,
    )
    db_session.add(resume)
    db_session.commit()

    result = cleanup_resume_pdfs(db_session, resumes_dir)

    assert result == {"removed": 0, "skipped": 1}
    assert txt_file.exists(), "Non-PDF file must not be deleted"


def test_cleanup_rejects_absolute_path_and_path_traversal(
    db_session: Session, tmp_path
):
    resumes_dir = tmp_path / "resumes"
    resumes_dir.mkdir(parents=True, exist_ok=True)
    outside_file = tmp_path / "outside.pdf"
    outside_file.write_bytes(b"%PDF-1.4 dummy content")

    vacancy = Vacancy(
        title="Job trying path traversal",
        text="Sample text",
        submit_email="test@example.com",
        source=DataSource.linkedin,
        visa_status=VisaStatus.not_required,
        status=VacancyStatus.created,
    )
    db_session.add(vacancy)
    db_session.commit()

    resume1 = Resume(
        fullname="John Doe",
        email="john@example.com",
        summary="Summary",
        path="../outside.pdf",
        vacancy_id=vacancy.id,
    )
    other_vacancy = Vacancy(
        title="Second invalid path vacancy",
        text="Sample text",
        submit_email="other@example.com",
        source=DataSource.linkedin,
        visa_status=VisaStatus.not_required,
        status=VacancyStatus.created,
    )
    db_session.add(other_vacancy)
    db_session.commit()
    resume2 = Resume(
        fullname="John Doe",
        email="john@example.com",
        summary="Summary",
        path=str(outside_file),
        vacancy_id=other_vacancy.id,
    )
    db_session.add_all([resume1, resume2])
    db_session.commit()

    result = cleanup_resume_pdfs(db_session, resumes_dir)

    assert result == {"removed": 0, "skipped": 2}
    assert outside_file.exists(), "File outside resumes_dir must not be deleted"


def test_cleanup_rejects_directory_path(db_session: Session, tmp_path):
    resumes_dir = tmp_path / "resumes"
    resumes_dir.mkdir(parents=True, exist_ok=True)
    sub_dir = resumes_dir / "folder.pdf"
    sub_dir.mkdir()

    vacancy = Vacancy(
        title="Job with directory as path",
        text="Sample text",
        submit_email="test@example.com",
        source=DataSource.linkedin,
        visa_status=VisaStatus.not_required,
        status=VacancyStatus.created,
    )
    db_session.add(vacancy)
    db_session.commit()

    resume = Resume(
        fullname="John Doe",
        email="john@example.com",
        summary="Summary",
        path="folder.pdf",
        vacancy_id=vacancy.id,
    )
    db_session.add(resume)
    db_session.commit()

    result = cleanup_resume_pdfs(db_session, resumes_dir)

    assert result == {"removed": 0, "skipped": 1}
    assert sub_dir.exists(), "Directory path must not be deleted"


def test_cleanup_handles_nonexistent_resumes_dir(db_session: Session, tmp_path):
    non_existent = tmp_path / "non_existent_dir"
    result = cleanup_resume_pdfs(db_session, non_existent)
    assert result == {"removed": 0, "skipped": 0}


def test_cleanup_handles_none_and_dot_paths(db_session: Session, tmp_path):
    resumes_dir = tmp_path / "resumes"
    resumes_dir.mkdir(parents=True, exist_ok=True)

    vacancy = Vacancy(
        title="Job with invalid resume paths",
        text="Sample text",
        submit_email="test@example.com",
        source=DataSource.linkedin,
        visa_status=VisaStatus.not_required,
        status=VacancyStatus.created,
    )
    db_session.add(vacancy)
    db_session.commit()

    resume_none = Resume(
        fullname="John Doe",
        email="john@example.com",
        summary="Summary",
        path=None,
        vacancy_id=vacancy.id,
    )
    other_vacancy = Vacancy(
        title="Second invalid resume path",
        text="Sample text",
        submit_email="other@example.com",
        source=DataSource.linkedin,
        visa_status=VisaStatus.not_required,
        status=VacancyStatus.created,
    )
    db_session.add(other_vacancy)
    db_session.commit()
    resume_dot = Resume(
        fullname="John Doe",
        email="john@example.com",
        summary="Summary",
        path=".",
        vacancy_id=other_vacancy.id,
    )
    db_session.add_all([resume_none, resume_dot])
    db_session.commit()

    result = cleanup_resume_pdfs(db_session, resumes_dir)

    assert result == {"removed": 0, "skipped": 2}
