from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from ljpa_reworked.database import Base, init_db
from ljpa_reworked.models.crewai_pydantic_models import BasicEvaluationCrewAI
from ljpa_reworked.models.database_models import BasicEvaluation
from ljpa_reworked.models.enums import VacancyStatus
from ljpa_reworked.operations.vacancy_ops import create_vacancy_direct


def test_existing_passing_evaluation_without_resume_creates_resume_without_reevaluation():
    from ljpa_reworked.main import process_unevaluated_vacancies

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(bind_engine=engine)
    db = sessionmaker(bind=engine)()
    try:
        vacancy = create_vacancy_direct(
            db,
            title="Controls Engineer",
            text="PLC vacancy",
            submit_url="https://example.com/jobs/controls",
        )
        db.add(BasicEvaluation(vacancy_id=vacancy.id, rating=80, summary="match"))
        db.commit()
        evaluation = BasicEvaluationCrewAI(rating=80, summary="match")

        with (
            patch("ljpa_reworked.main.crewai_evaluate_vacancy") as evaluate,
            patch(
                "ljpa_reworked.main.crewai_generate_resume",
                return_value="resume",
            ) as generate,
            patch("ljpa_reworked.main.save_resume") as save,
        ):
            process_unevaluated_vacancies(db)

        evaluate.assert_not_called()
        generate.assert_called_once_with(vacancy=vacancy, evaluation=evaluation)
        save.assert_called_once()
        assert (
            db.get(type(vacancy), vacancy.id).status
            == VacancyStatus.application_prepared
        )
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
