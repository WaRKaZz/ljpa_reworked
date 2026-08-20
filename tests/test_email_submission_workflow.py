from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from ljpa_reworked.database import Base, init_db
from ljpa_reworked.models.crewai_pydantic_models import EmailCrewAI
from ljpa_reworked.models.database_models import BasicEvaluation, Email, Resume, Vacancy
from ljpa_reworked.models.enums import VacancyStatus
from ljpa_reworked.operations import confirm_url_application_submitted
from ljpa_reworked.operations.evaluation_ops import (
    build_ranked_email_submission_queue,
    build_ranked_submission_queue,
)
from ljpa_reworked.operations.vacancy_ops import create_vacancy_direct


def _session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(bind_engine=engine)
    return sessionmaker(bind=engine)(), engine


def _evaluation(db, vacancy, rating, visa_prob=100):
    db.add(
        BasicEvaluation(
            vacancy_id=vacancy.id,
            rating=rating,
            visa_probability=visa_prob,
            summary="evaluation match",
        )
    )
    db.commit()


def test_build_ranked_email_submission_queue_ranks_and_filters():
    db, engine = _session()
    try:
        now = datetime(2026, 8, 16, 12, 0, 0)
        # 1. Fresh high rating email vacancy
        v1 = create_vacancy_direct(
            db,
            title="Senior Python Dev",
            text="Python job description",
            submit_email="hr1@example.com",
            submit_url="https://example.com/job1",
        )
        v1.created_at = now
        v1.status = VacancyStatus.application_prepared
        db.add(
            Resume(
                vacancy_id=v1.id, fullname="Test", email="test@ex.com", summary="Test"
            )
        )

        # 2. Older email vacancy
        v2 = create_vacancy_direct(
            db,
            title="Lead Engineer",
            text="Lead job description",
            submit_email="hr2@example.com",
        )
        v2.created_at = now - timedelta(days=2)
        v2.status = VacancyStatus.application_prepared
        db.add(
            Resume(
                vacancy_id=v2.id, fullname="Test", email="test@ex.com", summary="Test"
            )
        )

        # 3. Low score email vacancy (should be filtered out & deleted)
        v3 = create_vacancy_direct(
            db,
            title="Low Match Job",
            text="Low job description",
            submit_email="hr3@example.com",
        )
        v3.created_at = now
        v3.status = VacancyStatus.application_prepared
        db.add(
            Resume(
                vacancy_id=v3.id, fullname="Test", email="test@ex.com", summary="Test"
            )
        )

        # 4. URL-only vacancy (no email, should NOT be in email queue)
        v4 = create_vacancy_direct(
            db,
            title="URL Only Job",
            text="URL only description",
            submit_url="https://example.com/job4",
        )
        v4.created_at = now
        v4.status = VacancyStatus.application_prepared
        db.add(
            Resume(
                vacancy_id=v4.id, fullname="Test", email="test@ex.com", summary="Test"
            )
        )

        # 5. Already submitted via email (should NOT be in email queue)
        v5 = create_vacancy_direct(
            db,
            title="Already Emailed",
            text="Already emailed description",
            submit_email="hr5@example.com",
        )
        v5.created_at = now
        v5.status = VacancyStatus.submitted_via_email
        db.add(
            Resume(
                vacancy_id=v5.id, fullname="Test", email="test@ex.com", summary="Test"
            )
        )

        # 6. Submitted via URL, but has email (CAN be in email queue)
        v6 = create_vacancy_direct(
            db,
            title="URL Submitted But Has Email",
            text="Dual contact description",
            submit_email="hr6@example.com",
            submit_url="https://example.com/job6",
        )
        v6.created_at = now
        v6.status = VacancyStatus.submitted_via_url
        db.add(
            Resume(
                vacancy_id=v6.id, fullname="Test", email="test@ex.com", summary="Test"
            )
        )

        _evaluation(db, v1, rating=90)
        _evaluation(db, v2, rating=95)  # 95 - 2*1.5 = 92
        _evaluation(db, v3, rating=40)  # score < 50
        _evaluation(db, v4, rating=90)
        _evaluation(db, v5, rating=90)
        _evaluation(db, v6, rating=85)

        ranked = build_ranked_email_submission_queue(db, now=now)

        # Expected order: v2 (92.0), v1 (90.0), v6 (85.0)
        ranked_ids = [item.vacancy.id for item in ranked]
        assert ranked_ids == [v2.id, v1.id, v6.id]
        assert [(item.vacancy.id, item.score) for item in ranked] == [
            (v2.id, 92.0),
            (v1.id, 90.0),
            (v6.id, 85.0),
        ]
        # v3 soft-deleted
        assert db.get(Vacancy, v3.id).deleted is True
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_url_queue_allows_submitted_via_email_vacancies():
    db, engine = _session()
    try:
        now = datetime(2026, 8, 16, 12, 0, 0)
        # Vacancy submitted by email that also has submit_url
        v1 = create_vacancy_direct(
            db,
            title="Dual Vacancy Emailed",
            text="Job text",
            submit_email="hr@example.com",
            submit_url="https://example.com/job1",
        )
        v1.created_at = now
        v1.status = VacancyStatus.submitted_via_email
        v1.applied_at = now
        db.add(
            Resume(
                vacancy_id=v1.id, fullname="Test", email="test@ex.com", summary="Test"
            )
        )

        # Vacancy submitted via URL (should NOT be in URL queue)
        v2 = create_vacancy_direct(
            db,
            title="Already URL Submitted",
            text="Job text 2",
            submit_url="https://example.com/job2",
        )
        v2.created_at = now
        v2.status = VacancyStatus.submitted_via_url
        v2.applied_at = now
        db.add(
            Resume(
                vacancy_id=v2.id, fullname="Test", email="test@ex.com", summary="Test"
            )
        )

        # Vacancy submitted via all (should NOT be in URL queue)
        v3 = create_vacancy_direct(
            db,
            title="Already All Submitted",
            text="Job text 3",
            submit_url="https://example.com/job3",
        )
        v3.created_at = now
        v3.status = VacancyStatus.submitted_via_all
        v3.applied_at = now
        db.add(
            Resume(
                vacancy_id=v3.id, fullname="Test", email="test@ex.com", summary="Test"
            )
        )

        _evaluation(db, v1, rating=88)
        _evaluation(db, v2, rating=90)
        _evaluation(db, v3, rating=92)

        ranked = build_ranked_submission_queue(db, now=now)
        assert [item.vacancy.id for item in ranked] == [v1.id]
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_submit_top_email_vacancies_sends_emails_and_updates_status(
    monkeypatch, tmp_path
):
    from ljpa_reworked import main

    db, engine = _session()
    try:
        resumes_dir = tmp_path / "resumes"
        resumes_dir.mkdir()
        monkeypatch.setattr(main, "SUBMISSION_RESUMES_DIR", str(resumes_dir))

        vacancies = []
        for i in range(6):
            v = create_vacancy_direct(
                db,
                title=f"Engineer {i}",
                text=f"Description {i}",
                submit_email=f"recruiter{i}@company.com",
            )
            v.status = VacancyStatus.application_prepared
            _evaluation(db, v, rating=99 - i)
            (resumes_dir / f"resume_{v.id}.pdf").write_bytes(b"%PDF-1.4")
            db.add(
                Resume(
                    vacancy_id=v.id,
                    fullname="Applicant",
                    email="applicant@example.com",
                    summary="Summary",
                    path=f"resume_{v.id}.pdf",
                )
            )
            vacancies.append(v)
        db.commit()

        sent_emails = []

        def mock_generate_email(vacancy):
            return EmailCrewAI(
                subject=f"Application for {vacancy.title}",
                body=f"Dear Hiring Team, applying for {vacancy.title}",
            )

        def mock_send_email(email):
            sent_emails.append(email)

        monkeypatch.setattr(main, "crewai_generate_email", mock_generate_email)
        monkeypatch.setattr(main, "send_email", mock_send_email)

        count = main.submit_top_email_vacancies(db, limit=5)
        assert count == 5
        assert len(sent_emails) == 5

        # Check top 5 status
        for v in vacancies[:5]:
            db_v = db.get(Vacancy, v.id)
            assert db_v.status == VacancyStatus.submitted_via_email
            assert db_v.applied_at is not None
            email_records = db.query(Email).filter(Email.vacancy_id == v.id).all()
            assert len(email_records) == 1
            assert email_records[0].sent is True
            assert email_records[0].recipient == v.submit_email

        # 6th vacancy was not submitted
        db_v6 = db.get(Vacancy, vacancies[5].id)
        assert db_v6.status == VacancyStatus.application_prepared
        assert db.query(Email).filter(Email.vacancy_id == vacancies[5].id).count() == 0
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_dual_channel_vacancy_transitions_to_submitted_via_all(monkeypatch, tmp_path):
    from ljpa_reworked import main

    db, engine = _session()
    try:
        resumes_dir = tmp_path / "resumes"
        resumes_dir.mkdir()
        monkeypatch.setattr(main, "SUBMISSION_RESUMES_DIR", str(resumes_dir))

        v = create_vacancy_direct(
            db,
            title="Dual Channel Job",
            text="Desc",
            submit_email="hr@dual.com",
            submit_url="https://dual.com/apply",
        )
        v.status = VacancyStatus.application_prepared
        _evaluation(db, v, rating=95)
        (resumes_dir / f"resume_{v.id}.pdf").write_bytes(b"%PDF-1.4")
        db.add(
            Resume(
                vacancy_id=v.id,
                fullname="Applicant",
                email="applicant@example.com",
                summary="Summary",
                path=f"resume_{v.id}.pdf",
            )
        )
        db.commit()

        monkeypatch.setattr(
            main,
            "crewai_generate_email",
            lambda vacancy: EmailCrewAI(subject="Subject", body="Body"),
        )
        monkeypatch.setattr(main, "send_email", lambda email: None)

        # 1. Email submission runs
        count = main.submit_top_email_vacancies(db, limit=5)
        assert count == 1
        assert db.get(Vacancy, v.id).status == VacancyStatus.submitted_via_email

        # 2. URL queue still contains this vacancy
        url_queue = build_ranked_submission_queue(db)
        assert [item.vacancy.id for item in url_queue] == [v.id]

        # 3. URL submission succeeds
        confirm_url_application_submitted(db, v.id)
        assert db.get(Vacancy, v.id).status == VacancyStatus.submitted_via_all
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_submit_top_email_vacancies_handles_error_gracefully(monkeypatch, tmp_path):
    from ljpa_reworked import main

    db, engine = _session()
    try:
        resumes_dir = tmp_path / "resumes"
        resumes_dir.mkdir()
        monkeypatch.setattr(main, "SUBMISSION_RESUMES_DIR", str(resumes_dir))

        v1 = create_vacancy_direct(
            db,
            title="Job 1 (Error)",
            text="Desc 1",
            submit_email="error@company.com",
        )
        v1.status = VacancyStatus.application_prepared
        _evaluation(db, v1, rating=95)
        (resumes_dir / f"resume_{v1.id}.pdf").write_bytes(b"%PDF-1.4")
        db.add(
            Resume(
                vacancy_id=v1.id,
                fullname="Applicant",
                email="applicant@example.com",
                summary="Summary",
                path=f"resume_{v1.id}.pdf",
            )
        )

        v2 = create_vacancy_direct(
            db,
            title="Job 2 (Success)",
            text="Desc 2",
            submit_email="success@company.com",
        )
        v2.status = VacancyStatus.application_prepared
        _evaluation(db, v2, rating=90)
        (resumes_dir / f"resume_{v2.id}.pdf").write_bytes(b"%PDF-1.4")
        db.add(
            Resume(
                vacancy_id=v2.id,
                fullname="Applicant",
                email="applicant@example.com",
                summary="Summary",
                path=f"resume_{v2.id}.pdf",
            )
        )
        db.commit()

        def flaky_send_email(email):
            if "error@" in email.recipient:
                raise RuntimeError("SMTP connection timeout")

        monkeypatch.setattr(
            main,
            "crewai_generate_email",
            lambda vacancy: EmailCrewAI(subject="Subject", body="Body"),
        )
        monkeypatch.setattr(main, "send_email", flaky_send_email)

        count = main.submit_top_email_vacancies(db, limit=5)
        # 1 successfully submitted out of 2 attempts
        assert count == 1
        assert db.get(Vacancy, v1.id).status == VacancyStatus.application_error
        assert db.get(Vacancy, v2.id).status == VacancyStatus.submitted_via_email
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_has_recent_sent_email_to_recipient():
    from ljpa_reworked.operations.email_ops import has_recent_sent_email_to_recipient

    db, engine = _session()
    try:
        now = datetime(2026, 8, 20, 12, 0, 0)
        v = create_vacancy_direct(
            db, title="Test Job", text="Text", submit_email="hr@test.com"
        )

        # Unsent email within 30 days
        e1 = Email(
            vacancy_id=v.id,
            subject="Subj 1",
            recipient="hr@test.com",
            sent=False,
            created_at=now - timedelta(days=5),
        )
        db.add(e1)
        db.commit()
        assert not has_recent_sent_email_to_recipient(
            db, "hr@test.com", days=30, now=now
        )

        # Sent email > 30 days ago
        e2 = Email(
            vacancy_id=v.id,
            subject="Subj 2",
            recipient="hr@old.com",
            sent=True,
            created_at=now - timedelta(days=31),
        )
        db.add(e2)
        db.commit()
        assert not has_recent_sent_email_to_recipient(
            db, "hr@old.com", days=30, now=now
        )

        # Sent email <= 30 days ago
        e3 = Email(
            vacancy_id=v.id,
            subject="Subj 3",
            recipient="hr@recent.com",
            sent=True,
            created_at=now - timedelta(days=10),
        )
        db.add(e3)
        db.commit()
        assert has_recent_sent_email_to_recipient(
            db, "hr@recent.com", days=30, now=now
        )

        # Whitespace handling
        assert has_recent_sent_email_to_recipient(
            db, "  hr@recent.com  ", days=30, now=now
        )
        # Empty recipient
        assert not has_recent_sent_email_to_recipient(db, "", days=30, now=now)
        assert not has_recent_sent_email_to_recipient(db, None, days=30, now=now)
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

