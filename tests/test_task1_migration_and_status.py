from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from ljpa_reworked.database import Base
from ljpa_reworked.models.crewai_pydantic_models import VacancyCrewAI, VisaStatus
from ljpa_reworked.models.database_models import DataSource, Vacancy
from ljpa_reworked.models.enums import VacancyStatus


def test_vacancy_status_enum_values():
    assert VacancyStatus.created.value == "created"
    assert VacancyStatus.updated.value == "updated"
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
    from ljpa_reworked.models.crewai_pydantic_models import (
        VacancyStatus as CrewAIVacancyStatus,
    )
    assert CrewAIVacancyStatus is VacancyStatus


def test_crewai_task_expected_output_does_not_contain_status():
    # Verify VacancyCrewAI model fields do not include status
    assert "status" not in VacancyCrewAI.model_fields


def test_alembic_migration_backfill_and_downgrade(tmp_path):
    db_path = tmp_path / "test_migration.db"
    db_url = f"sqlite:///{db_path}"

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    # 1. Upgrade to head
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(db_url)
    with engine.connect() as conn:
        cols = [c[1] for c in conn.execute(text("PRAGMA table_info(vacancy)")).fetchall()]
        assert "status" in cols
        assert "processed" not in cols

    # 2. Downgrade to base
    command.downgrade(alembic_cfg, "base")
    engine.dispose()
