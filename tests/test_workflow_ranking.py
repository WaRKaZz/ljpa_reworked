import json
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from ljpa_reworked.database import Base, init_db
from ljpa_reworked.models.crewai_pydantic_models import BasicEvaluationCrewAI
from ljpa_reworked.models.database_models import BasicEvaluation
from ljpa_reworked.models.enums import VacancyStatus
from ljpa_reworked.operations.vacancy_ops import create_vacancy_direct


def _session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(bind_engine=engine)
    return sessionmaker(bind=engine)(), engine


def _vacancy(db, title):
    return create_vacancy_direct(
        db,
        title=title,
        text=f"{title} text",
        submit_url=f"https://example.com/{title.lower().replace(' ', '-')}",
    )


def _evaluation(db, vacancy, rating):
    db.add(BasicEvaluation(vacancy_id=vacancy.id, rating=rating, summary="match"))
    db.commit()


def test_ranked_submission_queue_penalizes_age_and_soft_deletes_below_fifty():
    from ljpa_reworked.operations.evaluation_ops import build_ranked_submission_queue

    db, engine = _session()
    try:
        now = datetime(2026, 8, 13, 12, 0, 0)
        fresh = _vacancy(db, "Fresh")
        two_days_old = _vacancy(db, "Two Days")
        raw_low = _vacancy(db, "Raw Low")
        penalized_low = _vacancy(db, "Penalized Low")
        for vacancy, age in (
            (fresh, 0),
            (two_days_old, 2),
            (raw_low, 0),
            (penalized_low, 2),
        ):
            vacancy.created_at = now - timedelta(days=age)
            vacancy.status = VacancyStatus.application_prepared
        _evaluation(db, fresh, 88)
        _evaluation(db, two_days_old, 90)
        _evaluation(db, raw_low, 49)
        _evaluation(db, penalized_low, 51)

        ranked = build_ranked_submission_queue(db, now=now)

        assert [(item.vacancy.id, item.score) for item in ranked] == [
            (fresh.id, 88.0),
            (two_days_old.id, 87.0),
        ]
        assert db.get(type(raw_low), raw_low.id).deleted is True
        assert db.get(type(penalized_low), penalized_low.id).deleted is True
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_processes_only_unevaluated_vacancies_and_creates_resume_for_passing_match(
    monkeypatch,
):
    from ljpa_reworked import main

    db, engine = _session()
    try:
        evaluated = _vacancy(db, "Already Evaluated")
        pending = _vacancy(db, "Pending")
        _evaluation(db, evaluated, 80)
        evaluation = BasicEvaluationCrewAI(rating=80, summary="match")
        monkeypatch.setattr(main, "crewai_evaluate_vacancy", lambda vacancy: evaluation)
        calls = []
        monkeypatch.setattr(
            main,
            "crewai_generate_resume_with_retry",
            lambda vacancy, evaluation: ("resume", "/tmp/test-resume.pdf"),
        )

        def fake_persist(_resume, vacancy, session, _pdf_path):
            calls.append(vacancy)
            vacancy.status = VacancyStatus.application_prepared
            session.commit()

        monkeypatch.setattr(main, "persist_prepared_resume", fake_persist)

        main.process_unevaluated_vacancies(db)

        assert calls == [evaluated, pending]
        assert (
            db.get(type(evaluated), evaluated.id).status
            == VacancyStatus.application_prepared
        )
        assert (
            db.get(type(pending), pending.id).status
            == VacancyStatus.application_prepared
        )
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_submit_top_five_waits_three_hours_between_each_submission(
    monkeypatch, tmp_path
):
    from ljpa_reworked import main
    from ljpa_reworked.models.database_models import Resume

    db, engine = _session()
    try:
        vacancies = [_vacancy(db, f"Job {number}") for number in range(6)]
        for number, vacancy in enumerate(vacancies):
            vacancy.status = VacancyStatus.application_prepared
            _evaluation(db, vacancy, 100 - number)
            db.add(
                Resume(
                    vacancy_id=vacancy.id,
                    fullname="Test User",
                    email="test@example.com",
                    summary="Test summary",
                    path=f"resume_{number}.pdf",
                )
            )
        db.commit()
        resumes_dir = tmp_path / "resumes"
        resumes_dir.mkdir()
        for number in range(6):
            (resumes_dir / f"resume_{number}.pdf").write_bytes(b"%PDF-1.4")
        sleeps = []
        submitted = []
        monkeypatch.setattr(main, "SUBMISSION_RESUMES_DIR", str(resumes_dir))
        monkeypatch.setattr(main, "time", type("Clock", (), {"sleep": sleeps.append}))
        monkeypatch.setattr(main, "get_gemini_quota_remaining", lambda api_url: 1.0)
        monkeypatch.setattr(
            main,
            "render_resume_crewai_to_pdf",
            lambda resume_crewai, pdf_path: None,
        )
        monkeypatch.setattr(
            main,
            "harness_submit",
            lambda **kwargs: submitted.append(kwargs["vacancy_url"]) or 0,
        )

        assert main.submit_top_vacancies(db) == 0

        assert submitted == [vacancy.submit_url for vacancy in vacancies[:5]]
        assert sleeps == [main.SUBMISSION_DELAY_SECONDS] * 4
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_harness_forces_flash_medium_model(monkeypatch):
    from ljpa_reworked.services import harness_runner

    request = {}

    class Response:
        def __enter__(self):
            return iter([b'{"status": "success"}\n'])

        def __exit__(self, *args):
            return False

    def urlopen(req):
        request["body"] = json.loads(req.data)
        return Response()

    monkeypatch.setattr(harness_runner.urllib.request, "urlopen", urlopen)
    assert harness_runner.harness_submit("https://example.com", "/tmp/resume.pdf") == 0
    assert request["body"]["model"] == "gemini-3.7-flash-medium"
