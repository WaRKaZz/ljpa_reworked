import inspect

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import sessionmaker

from ljpa_reworked import main as main_module
from ljpa_reworked.database import Base, init_db
from ljpa_reworked.models import database_models
from ljpa_reworked.models.database_models import DataSource, Vacancy
from ljpa_reworked.models.enums import VacancyStatus
from ljpa_reworked.operations.vacancy_ops import (
    get_eligble_vacancies,
    upsert_vacancy_by_url,
)


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database session for unit testing."""
    engine = create_engine("sqlite:///:memory:")
    init_db(bind_engine=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()


def test_orm_has_no_linkedin_post():
    """Verify ORM model, relationships, and Base metadata have no LinkedinPost or linkedin_post table."""
    assert not hasattr(database_models, "LinkedinPost"), (
        "LinkedinPost model should be deleted from database_models"
    )
    assert not hasattr(Vacancy, "linkedin_posts"), (
        "Vacancy should not have linkedin_posts relationship"
    )
    assert "linkedin_post" not in Base.metadata.tables, (
        "linkedin_post table should not exist in Base.metadata"
    )


def test_new_direct_upsert_creates_created_status(db_session):
    """Verify upserting a new vacancy URL sets status=created and returns is_created=True."""
    v, is_created = upsert_vacancy_by_url(
        db_session,
        {
            "title": "Senior Python Developer",
            "text": "Join our team to write Python code.",
            "submit_email": "recruiter@example.com",
            "submit_url": "https://www.linkedin.com/jobs/view/10001/",
            "source": DataSource.linkedin,
        },
    )
    assert is_created is True
    assert v is not None
    assert v.status == VacancyStatus.created
    assert v.title == "Senior Python Developer"


def test_matching_url_upsert_refreshes_source_fields_and_sets_updated_status(
    db_session,
):
    """Verify upserting an existing vacancy URL refreshes fields and sets status=updated."""
    v_initial, is_created1 = upsert_vacancy_by_url(
        db_session,
        {
            "title": "Initial Title",
            "text": "Initial text content",
            "submit_email": "old@example.com",
            "submit_url": "https://www.linkedin.com/jobs/view/10002/",
            "source": DataSource.linkedin,
        },
    )
    assert is_created1 is True
    assert v_initial.status == VacancyStatus.created

    v_updated, is_created2 = upsert_vacancy_by_url(
        db_session,
        {
            "title": "Updated Title",
            "text": "Updated text content",
            "submit_email": "new@example.com",
            "submit_url": "https://www.linkedin.com/jobs/view/10002/",
            "source": DataSource.linkedin,
        },
    )
    assert is_created2 is False
    assert v_updated.id == v_initial.id
    assert v_updated.title == "Updated Title"
    assert v_updated.text == "Updated text content"
    assert v_updated.submit_email == "new@example.com"
    assert v_updated.status == VacancyStatus.updated


def test_eligible_vacancies_includes_created_updated_and_review_error(db_session):
    """Verify get_eligble_vacancies includes created, updated, and review_error statuses."""
    from ljpa_reworked.models.crewai_pydantic_models import VisaStatus

    v_created = Vacancy(
        title="Job 1",
        text="Text 1",
        submit_email="c1@example.com",
        submit_url="https://example.com/job/1",
        status=VacancyStatus.created,
        source=DataSource.linkedin,
        visa_status=VisaStatus.not_mentioned,
    )

    if hasattr(VacancyStatus, "updated"):
        v_updated = Vacancy(
            title="Job 2",
            text="Text 2",
            submit_email="c2@example.com",
            submit_url="https://example.com/job/2",
            status=VacancyStatus.updated,
            source=DataSource.linkedin,
            visa_status=VisaStatus.not_mentioned,
        )
        db_session.add(v_updated)

    v_error = Vacancy(
        title="Job 3",
        text="Text 3",
        submit_email="c3@example.com",
        submit_url="https://example.com/job/3",
        status=VacancyStatus.review_error,
        source=DataSource.linkedin,
        visa_status=VisaStatus.not_mentioned,
    )
    v_reviewed = Vacancy(
        title="Job 4",
        text="Text 4",
        submit_email="c4@example.com",
        submit_url="https://example.com/job/4",
        status=VacancyStatus.reviewed,
        source=DataSource.linkedin,
        visa_status=VisaStatus.not_mentioned,
    )
    db_session.add_all([v_created, v_error, v_reviewed])
    db_session.commit()

    eligible = get_eligble_vacancies(db_session)
    eligible_ids = {v.id for v in eligible}

    assert v_created.id in eligible_ids
    assert v_error.id in eligible_ids
    assert v_reviewed.id not in eligible_ids
    if hasattr(VacancyStatus, "updated"):
        assert v_updated.id in eligible_ids


def test_main_does_not_process_raw_posts():
    """Verify main module source code no longer references get_linkedin_posts or process_linkedin_posts."""
    source_code = inspect.getsource(main_module.main)
    assert "get_linkedin_posts" not in source_code
    assert "process_linkedin_posts" not in source_code
    assert "save_vacancies" not in source_code


def test_fresh_bootstrap_has_no_linkedin_post(tmp_path):
    """Verify metadata bootstrap creates disposable DB cleanly with no linkedin_post table."""
    db_path = tmp_path / "fresh_test.db"
    db_url = f"sqlite:///{db_path}"

    engine = create_engine(db_url)
    init_db(bind_engine=engine)
    inspector = sa_inspect(engine)
    tables = inspector.get_table_names()

    assert "vacancy" in tables
    assert "linkedin_post" not in tables

    with engine.connect() as conn:
        res = conn.execute(text("PRAGMA integrity_check;")).scalar()
        assert res == "ok"

    engine.dispose()
