import os
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from ljpa_reworked.models.database_models import Resume
from ljpa_reworked.models.enums import VacancyStatus


def cleanup_resume_pdfs(
    db: Session,
    resumes_dir: str | Path,
    now: datetime | None = None,
) -> dict[str, int]:
    """Clean up PDF resume files for unsubmitted or stale applied vacancies.

    Safety rules:
    - Only delete PDF files within resumes_dir.
    - Reject absolute paths, path traversal (e.g. '..'), non-.pdf extension, and directories.
    - Delete PDF if vacancy status is not applied OR applied_at is older than 60 days.
    - Retain PDF if vacancy status is applied AND applied_at is within 60 days.
    - Do NOT delete or modify any DB records.
    """
    if now is None:
        now = datetime.utcnow()

    resumes_dir_path = Path(resumes_dir).resolve()
    if not resumes_dir_path.exists() or not resumes_dir_path.is_dir():
        return {"removed": 0, "skipped": 0}

    resumes = db.query(Resume).all()
    removed_count = 0
    skipped_count = 0

    for resume in resumes:
        rel_path_str = resume.path
        if not rel_path_str or not isinstance(rel_path_str, str):
            skipped_count += 1
            continue

        rel_path_str = rel_path_str.strip()

        if os.path.isabs(rel_path_str) or not rel_path_str.lower().endswith(".pdf"):
            skipped_count += 1
            continue

        target_path = (resumes_dir_path / rel_path_str).resolve()
        try:
            target_path.relative_to(resumes_dir_path)
        except ValueError:
            skipped_count += 1
            continue

        if target_path == resumes_dir_path:
            skipped_count += 1
            continue

        if not target_path.exists() or not target_path.is_file():
            skipped_count += 1
            continue

        vacancy = resume.vacancy
        should_retain = False
        if (
            vacancy
            and vacancy.status == VacancyStatus.applied
            and vacancy.applied_at is not None
        ):
            age = now - vacancy.applied_at
            if age <= timedelta(days=60):
                should_retain = True

        if should_retain:
            skipped_count += 1
        else:
            try:
                target_path.unlink()
                removed_count += 1
            except OSError:
                skipped_count += 1

    return {"removed": removed_count, "skipped": skipped_count}
