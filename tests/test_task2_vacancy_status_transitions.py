import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from ljpa_reworked.database import Base, init_db
from ljpa_reworked.models.enums import VacancyStatus
from ljpa_reworked.operations.vacancy_ops import (
    create_vacancy_direct,
    get_eligble_vacancies,
    transition_vacancy_status,
    update_vacancy,
)


@pytest.fixture
def db_session():
    """SQLite in-memory database session fixture."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(bind_engine=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_get_eligible_vacancies_status_filter(db_session):
    """Query test that returns only created, updated, and review_error for review queue."""
    v1 = create_vacancy_direct(
        db=db_session,
        title="Created Job",
        text="Text 1",
        submit_email="hr1@company.com",
    )
    v2 = create_vacancy_direct(
        db=db_session, title="Error Job", text="Text 2", submit_email="hr2@company.com"
    )
    v3 = create_vacancy_direct(
        db=db_session,
        title="Reviewed Job",
        text="Text 3",
        submit_email="hr3@company.com",
    )
    v4 = create_vacancy_direct(
        db=db_session,
        title="Rejected Job",
        text="Text 4",
        submit_email="hr4@company.com",
    )

    transition_vacancy_status(db_session, v2.id, VacancyStatus.review_error)
    transition_vacancy_status(db_session, v3.id, VacancyStatus.reviewed)
    transition_vacancy_status(db_session, v4.id, VacancyStatus.rejected)

    eligible = get_eligble_vacancies(db_session)
    eligible_ids = {v.id for v in eligible}

    assert len(eligible) == 2
    assert eligible_ids == {v1.id, v2.id}


def test_valid_vacancy_status_transitions(db_session):
    """Test valid sequential status transitions."""
    v = create_vacancy_direct(
        db=db_session, title="Backend Dev", text="Text", submit_email="hr@company.com"
    )
    assert v.status == VacancyStatus.created

    t1 = transition_vacancy_status(db_session, v.id, VacancyStatus.reviewed)
    assert t1.status == VacancyStatus.reviewed

    t2 = transition_vacancy_status(db_session, v.id, VacancyStatus.application_prepared)
    assert t2.status == VacancyStatus.application_prepared

    t3 = transition_vacancy_status(db_session, v.id, VacancyStatus.applied)
    assert t3.status == VacancyStatus.applied


def test_transition_with_allowed_from_statuses_validation(db_session):
    """Test state validation when allowed_from_statuses is specified."""
    v = create_vacancy_direct(
        db=db_session, title="DevOps", text="Text", submit_email="hr@company.com"
    )
    assert v.status == VacancyStatus.created

    with pytest.raises(ValueError, match="is not allowed"):
        transition_vacancy_status(
            db_session,
            v.id,
            VacancyStatus.applied,
            allowed_from_statuses=[VacancyStatus.application_prepared],
        )

    # Status must remain created
    db_session.refresh(v)
    assert v.status == VacancyStatus.created


def test_terminal_status_protection(db_session):
    """Test that terminal statuses (applied, withdrawn, expired, archived) cannot be overwritten."""
    terminal_statuses = [
        VacancyStatus.applied,
        VacancyStatus.withdrawn,
        VacancyStatus.expired,
        VacancyStatus.archived,
    ]

    for term_status in terminal_statuses:
        v = create_vacancy_direct(
            db=db_session,
            title=f"Job {term_status.value}",
            text="Text",
            submit_email="hr@company.com",
        )
        # Direct assignment for setting up initial test state
        v.status = term_status
        db_session.commit()

        with pytest.raises(ValueError, match="terminal status"):
            transition_vacancy_status(db_session, v.id, VacancyStatus.reviewed)

        db_session.refresh(v)
        assert v.status == term_status


def test_update_vacancy_with_status_kwarg(db_session):
    """Test update_vacancy routes status change through transition logic."""
    v = create_vacancy_direct(
        db=db_session, title="PLC Dev", text="Text", submit_email="hr@company.com"
    )
    updated = update_vacancy(
        db_session, v.id, title="Updated Title", status=VacancyStatus.rejected
    )

    assert updated is not None
    assert updated.title == "Updated Title"
    assert updated.status == VacancyStatus.rejected
