from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from ljpa_reworked.database import Base, init_db
from ljpa_reworked.main import process_eligible_vacancies
from ljpa_reworked.models.database_models import Resume
from ljpa_reworked.operations.vacancy_ops import create_vacancy_direct


def test_existing_resume_skips_evaluation_and_generation():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(bind_engine=engine)
    session = sessionmaker(bind=engine)()
    try:
        vacancy = create_vacancy_direct(
            db=session,
            title="Controls Engineer",
            text="PLC vacancy",
            submit_email="jobs@example.com",
        )
        session.add(
            Resume(
                fullname="Ivan",
                email="ivan@example.com",
                summary="Prepared",
                vacancy_id=vacancy.id,
            )
        )
        session.commit()

        with patch("ljpa_reworked.main.crewai_evaluate_vacancy") as evaluate, patch(
            "ljpa_reworked.main.crewai_generate_resume_with_retry"
        ) as generate:
            process_eligible_vacancies(session, [vacancy])

        evaluate.assert_not_called()
        generate.assert_not_called()
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
