import pytest
from pathlib import Path
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from ljpa_reworked.database import Base
from ljpa_reworked.models.enums import VacancyStatus
from ljpa_reworked.models.database_models import Vacancy, DataSource
from ljpa_reworked.models.crewai_pydantic_models import VisaStatus, VacancyCrewAI


def test_vacancy_status_enum_values():
    assert VacancyStatus.created.value == "created"
    assert VacancyStatus.reviewed.value == "reviewed"
    assert VacancyStatus.rejected.value == "rejected"
    assert VacancyStatus.review_error.value == "review_error"
    assert VacancyStatus.application_prepared.value == "application_prepared"
    assert VacancyStatus.applied.value == "applied"
    assert VacancyStatus.application_error.value == "application_error"
    assert VacancyStatus.withdrawn.value == "withdrawn"
    assert VacancyStatus.expired.value == "expired"
    assert VacancyStatus.archived.value == "archived"


def test_vacancy_model_status_default():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    v = Vacancy(
        title="Test Title",
        text="Test Text",
        credentials="test@example.com",
        source=DataSource.linkedin,
        visa_status=VisaStatus.provided,
    )
    assert not hasattr(v, "processed")
    session.add(v)
    session.commit()

    assert hasattr(v, "status")
    assert v.status == VacancyStatus.created


def test_crewai_pydantic_models_reexports_vacancystatus():
    from ljpa_reworked.models.crewai_pydantic_models import VacancyStatus as CrewAIVacancyStatus
    assert CrewAIVacancyStatus is VacancyStatus


def test_crewai_task_expected_output_does_not_contain_status():
    # Verify VacancyCrewAI model fields do not include status
    assert "status" not in VacancyCrewAI.model_fields


def test_alembic_migration_backfill_and_downgrade(tmp_path):
    db_path = tmp_path / "test_migration.db"
    db_url = f"sqlite:///{db_path}"

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    # 1. Upgrade to previous head (5ca38e6b4f5a)
    command.upgrade(alembic_cfg, "5ca38e6b4f5a")

    # 2. Populate SQLite database with processed = 1 (true), 0 (false), and NULL
    engine = create_engine(db_url)
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO vacancy (title, text, credentials, source, visa_status, processed, deleted)
            VALUES ('Job True', 'Desc 1', 'cred1', 'LinkedIn', 'provided', 1, 0)
        """))
        conn.execute(text("""
            INSERT INTO vacancy (title, text, credentials, source, visa_status, processed, deleted)
            VALUES ('Job False', 'Desc 2', 'cred2', 'LinkedIn', 'provided', 0, 0)
        """))
        conn.execute(text("""
            INSERT INTO vacancy (title, text, credentials, source, visa_status, processed, deleted)
            VALUES ('Job Null', 'Desc 3', 'cred3', 'LinkedIn', 'provided', NULL, 0)
        """))
        conn.commit()

    # 3. Apply upgrade to head (4134f218d1f0)
    command.upgrade(alembic_cfg, "head")

    # 4. Verify status backfill and column changes
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT title, status FROM vacancy ORDER BY id")).fetchall()
        assert len(rows) == 3
        # processed=1 -> reviewed
        assert rows[0][0] == "Job True" and rows[0][1] == "reviewed"
        # processed=0 -> created
        assert rows[1][0] == "Job False" and rows[1][1] == "created"
        # processed=NULL -> created
        assert rows[2][0] == "Job Null" and rows[2][1] == "created"

        cols = [c[1] for c in conn.execute(text("PRAGMA table_info(vacancy)")).fetchall()]
        assert "status" in cols
        assert "processed" not in cols

    # 5. Test downgrade back to 5ca38e6b4f5a
    command.downgrade(alembic_cfg, "5ca38e6b4f5a")

    # 6. Verify processed status restore
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT title, processed FROM vacancy ORDER BY id")).fetchall()
        assert len(rows) == 3
        assert rows[0][0] == "Job True" and rows[0][1] == 1
        assert rows[1][0] == "Job False" and rows[1][1] == 0
        assert rows[2][0] == "Job Null" and rows[2][1] == 0

        cols = [c[1] for c in conn.execute(text("PRAGMA table_info(vacancy)")).fetchall()]
        assert "processed" in cols
        assert "status" not in cols

    engine.dispose()
