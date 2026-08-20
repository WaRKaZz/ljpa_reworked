from datetime import datetime
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ljpa_reworked.database import Base
from ljpa_reworked.models.crewai_pydantic_models import (
    BasicEvaluationCrewAI,
    VisaStatus,
)
from ljpa_reworked.models.database_models import (
    DataSource,
    Resume,
    Vacancy,
)
from ljpa_reworked.models.enums import VacancyStatus
from ljpa_reworked.operations.evaluation_ops import (
    build_ranked_submission_queue,
    create_evaluation,
)


def _setup_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    return session_factory(), engine


def test_resume_evaluation_crew_has_two_agents_and_two_tasks():
    from ljpa_reworked.crews.resume_evaluation_crew.resume_evaluation_crew import (
        ResumeEvaluationCrew,
    )

    crew_instance = ResumeEvaluationCrew()
    assert hasattr(crew_instance, "resume_evaluation_agent")
    assert hasattr(crew_instance, "visa_evaluation_agent")
    assert hasattr(crew_instance, "evaluate_resume_task")
    assert hasattr(crew_instance, "evaluate_visa_task")

    crew = crew_instance.crew()
    assert len(crew.agents) == 2
    assert len(crew.tasks) == 2


def test_crewai_evaluate_vacancy_parses_two_task_outputs(tmp_path):
    from ljpa_reworked.crew_workflow import crewai_evaluate_vacancy

    profile = tmp_path / "profile.md"
    profile.write_text(
        "## General Information\n- **Name:** A\n- **Target Title:** Controls Engineer\n- **Location:** A\n## Job Search Preferences\n- **Email:** a@example.com\n- **Phone:** 1\n## Summary\nSummary\n## Experience\n### Co — Engineer\n**Dates:** 2014 – Now\n**Location:** A\n- Source fact.\n## Education\n### U\n**Degree:** BSc\n**Dates:** 2010 – 2014\n## Skills\nSkills\n",
        encoding="utf-8",
    )

    task1_raw = """```json
{
  "summary": "Strong fit for the controls engineering role",
  "rating": 85,
  "required_profile_sections": ["Experience", "Skills"],
  "prioritized_facts": ["Siemens PLC experience"],
  "missing_mandatory_facts": []
}
```"""

    task2_raw = """```json
{
  "visa_probability": 90,
  "visa_reasoning": "Company regularly sponsors international engineers"
}
```"""

    task1_mock = MagicMock(raw=task1_raw, pydantic=None)
    task2_mock = MagicMock(raw=task2_raw, pydantic=None)
    output = MagicMock()
    output.raw = task2_raw
    output.pydantic = None
    output.tasks_output = [task1_mock, task2_mock]
    crew = MagicMock()
    crew.kickoff.return_value = output

    with (
        patch("ljpa_reworked.crew_workflow.PROFILE_FILE_PATH", str(profile)),
        patch("ljpa_reworked.crew_workflow.ResumeEvaluationCrew") as crew_class,
    ):
        crew_class.return_value.crew.return_value = crew
        vacancy = MagicMock(
            title="Controls Engineer",
            text="PLC role",
            submit_email="hr@example.com",
            submit_url="",
        )
        evaluation = crewai_evaluate_vacancy(vacancy)

    assert evaluation.summary == "Strong fit for the controls engineering role"
    assert evaluation.rating == 85
    assert evaluation.visa_probability == 90


def test_generate_missing_resumes_uses_visa_probability_formula():
    from ljpa_reworked.main import generate_missing_resumes

    db, engine = _setup_db()
    try:
        # Candidate 1: rating 60, visa_prob 100 -> score = 60 - 0 = 60 (> 50) -> should generate
        v1 = Vacancy(
            title="Pass 1",
            text="Text 1",
            source=DataSource.linkedin,
            visa_status=VisaStatus.NOT_SPECIFIED,
            submit_url="https://example.com/1",
        )
        # Candidate 2: rating 70, visa_prob 20 -> score = 70 - 80/2.2 = 70 - 36.36 = 33.64 (<= 50) -> should NOT generate
        v2 = Vacancy(
            title="Fail 2",
            text="Text 2",
            source=DataSource.linkedin,
            visa_status=VisaStatus.NOT_SPECIFIED,
            submit_url="https://example.com/2",
        )
        db.add_all([v1, v2])
        db.commit()

        create_evaluation(
            db,
            v1.id,
            BasicEvaluationCrewAI(summary="Good", rating=60, visa_probability=100),
        )
        create_evaluation(
            db,
            v2.id,
            BasicEvaluationCrewAI(summary="Low visa", rating=70, visa_probability=20),
        )

        with (
            patch("ljpa_reworked.main.crewai_generate_resume_with_retry") as mock_gen,
            patch("ljpa_reworked.main.persist_prepared_resume"),
        ):
            mock_gen.return_value = (MagicMock(), "/tmp/mock.pdf")
            generated_count = generate_missing_resumes(db)

            assert generated_count == 1
            mock_gen.assert_called_once()
            called_vacancy = mock_gen.call_args.kwargs["vacancy"]
            assert called_vacancy.id == v1.id
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_generate_missing_resumes_handles_multiple_evaluations_for_same_vacancy():
    from ljpa_reworked.main import generate_missing_resumes

    db, engine = _setup_db()
    try:
        v = Vacancy(
            title="Duplicate Eval Vacancy",
            text="Text",
            source=DataSource.linkedin,
            visa_status=VisaStatus.NOT_SPECIFIED,
            submit_url="https://example.com/dup",
        )
        db.add(v)
        db.commit()

        # Add 2 evaluations for the same vacancy
        create_evaluation(
            db,
            v.id,
            BasicEvaluationCrewAI(
                summary="First attempt", rating=60, visa_probability=100
            ),
        )
        create_evaluation(
            db,
            v.id,
            BasicEvaluationCrewAI(
                summary="Second attempt", rating=80, visa_probability=100
            ),
        )

        with (
            patch("ljpa_reworked.main.crewai_generate_resume_with_retry") as mock_gen,
            patch("ljpa_reworked.main.persist_prepared_resume"),
        ):
            mock_gen.return_value = (MagicMock(), "/tmp/mock.pdf")
            generated_count = generate_missing_resumes(db)

            # Must generate exactly once, not twice!
            assert generated_count == 1
            mock_gen.assert_called_once()
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_generate_missing_resumes_ignores_already_applied_or_terminal_vacancies():
    from ljpa_reworked.main import generate_missing_resumes

    db, engine = _setup_db()
    try:
        # Applied vacancy
        v1 = Vacancy(
            title="Applied Vacancy",
            text="Text",
            source=DataSource.linkedin,
            visa_status=VisaStatus.NOT_SPECIFIED,
            status=VacancyStatus.submitted_via_url,
            applied_at=datetime.now(),
            submit_url="https://example.com/app",
        )
        # Active unapplied vacancy
        v2 = Vacancy(
            title="Active Vacancy",
            text="Text",
            source=DataSource.linkedin,
            visa_status=VisaStatus.NOT_SPECIFIED,
            status=VacancyStatus.created,
            submit_url="https://example.com/active",
        )
        db.add_all([v1, v2])
        db.commit()

        create_evaluation(
            db,
            v1.id,
            BasicEvaluationCrewAI(summary="Fit", rating=90, visa_probability=100),
        )
        create_evaluation(
            db,
            v2.id,
            BasicEvaluationCrewAI(summary="Fit", rating=90, visa_probability=100),
        )

        with (
            patch("ljpa_reworked.main.crewai_generate_resume_with_retry") as mock_gen,
            patch("ljpa_reworked.main.persist_prepared_resume"),
        ):
            mock_gen.return_value = (MagicMock(), "/tmp/mock.pdf")
            generated_count = generate_missing_resumes(db)

            # Only v2 should have resume generated!
            assert generated_count == 1
            assert mock_gen.call_args.kwargs["vacancy"].id == v2.id
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_build_ranked_submission_queue_filters_only_vacancies_with_resumes_unapplied_and_no_errors():
    db, engine = _setup_db()
    try:
        now = datetime(2026, 8, 15, 12, 0, 0)
        # v1: Has resume, unapplied, application_prepared -> SHOULD BE IN QUEUE
        v1 = Vacancy(
            title="Valid Prepared",
            text="Text",
            source=DataSource.linkedin,
            visa_status=VisaStatus.NOT_SPECIFIED,
            submit_url="https://example.com/apply1",
            status=VacancyStatus.application_prepared,
            created_at=now,
        )
        # v2: NO resume, application_prepared -> SHOULD NOT BE IN QUEUE
        v2 = Vacancy(
            title="No Resume",
            text="Text",
            source=DataSource.linkedin,
            visa_status=VisaStatus.NOT_SPECIFIED,
            submit_url="https://example.com/apply2",
            status=VacancyStatus.application_prepared,
            created_at=now,
        )
        # v3: Has resume, but applied_at is set -> SHOULD NOT BE IN QUEUE
        v3 = Vacancy(
            title="Already Applied",
            text="Text",
            source=DataSource.linkedin,
            visa_status=VisaStatus.NOT_SPECIFIED,
            submit_url="https://example.com/apply3",
            status=VacancyStatus.submitted_via_url,
            applied_at=now,
            created_at=now,
        )
        # v4: Has resume, but status is application_error -> SHOULD NOT BE IN QUEUE
        v4 = Vacancy(
            title="Error Vacancy",
            text="Text",
            source=DataSource.linkedin,
            visa_status=VisaStatus.NOT_SPECIFIED,
            submit_url="https://example.com/apply4",
            status=VacancyStatus.application_error,
            created_at=now,
        )
        db.add_all([v1, v2, v3, v4])
        db.commit()

        # Add evaluations
        for v in (v1, v2, v3, v4):
            create_evaluation(
                db,
                v.id,
                BasicEvaluationCrewAI(summary="Eval", rating=80, visa_probability=100),
            )

        # Add Resume records for v1, v3, v4
        for v in (v1, v3, v4):
            r = Resume(
                vacancy_id=v.id,
                fullname="John",
                email="john@example.com",
                phone="123",
                address="City",
                summary="Dev",
            )
            db.add(r)
        db.commit()

        ranked = build_ranked_submission_queue(db, now=now)
        assert len(ranked) == 1
        assert ranked[0].vacancy.id == v1.id
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_format_visa_status_context():
    from ljpa_reworked.crew_workflow import format_visa_status_context

    # Provided status
    status_str, ctx = format_visa_status_context(VisaStatus.provided)
    assert status_str == "provided"
    assert "provides visa sponsorship" in ctx.lower()

    status_str, ctx = format_visa_status_context("provided")
    assert status_str == "provided"
    assert "provides visa sponsorship" in ctx.lower()

    # Not provided status
    status_str, ctx = format_visa_status_context(VisaStatus.not_provided)
    assert status_str == "not_provided"
    assert "not provide visa" in ctx.lower()

    # Not required status
    status_str, ctx = format_visa_status_context(VisaStatus.not_required)
    assert status_str == "not_required"
    assert "not required" in ctx.lower()

    # Not mentioned / specified / None
    status_str, ctx = format_visa_status_context(VisaStatus.not_mentioned)
    assert "not specified" in ctx.lower()

    status_str, ctx = format_visa_status_context(None)
    assert "not specified" in ctx.lower()


def test_crewai_evaluate_vacancy_passes_visa_status_in_inputs(tmp_path):
    from ljpa_reworked.crew_workflow import crewai_evaluate_vacancy

    profile = tmp_path / "profile.md"
    profile.write_text(
        "## General Information\n- **Name:** A\n- **Target Title:** Controls Engineer\n- **Location:** A\n## Job Search Preferences\n- **Email:** a@example.com\n- **Phone:** 1\n## Summary\nSummary\n## Experience\n### Co — Engineer\n**Dates:** 2014 – Now\n**Location:** A\n- Source fact.\n## Education\n### U\n**Degree:** BSc\n**Dates:** 2010 – 2014\n## Skills\nSkills\n",
        encoding="utf-8",
    )

    crew = MagicMock()
    output = MagicMock()
    output.pydantic = BasicEvaluationCrewAI(
        summary="Matches profile with visa", rating=90, visa_probability=95
    )
    crew.kickoff.return_value = output

    with (
        patch("ljpa_reworked.crew_workflow.PROFILE_FILE_PATH", str(profile)),
        patch("ljpa_reworked.crew_workflow.ResumeEvaluationCrew") as crew_class,
    ):
        crew_class.return_value.crew.return_value = crew
        vacancy = MagicMock(
            title="Backend Engineer",
            text="Python vacancy",
            submit_email="hr@example.com",
            submit_url="",
            visa_status=VisaStatus.provided,
        )
        evaluation = crewai_evaluate_vacancy(vacancy)

    assert evaluation.rating == 90
    assert evaluation.visa_probability == 95
    crew.kickoff.assert_called_once()
    passed_inputs = crew.kickoff.call_args[1]["inputs"]
    assert passed_inputs["visa_status"] == "provided"
    assert "provides visa sponsorship" in passed_inputs["visa_status_context"].lower()
