from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ljpa_reworked.database import Base
from ljpa_reworked.main import submit_top_vacancies
from ljpa_reworked.models.crewai_pydantic_models import (
    CertificationCrewAI,
    EducationCrewAI,
    ExperienceCrewAI,
    PersonalInfoCrewAI,
    ProjectCrewAI,
    ResumeCrewAI,
    SkillCrewAI,
    SubmissionReviewCrewAI,
)
from ljpa_reworked.models.database_models import BasicEvaluation, Vacancy
from ljpa_reworked.models.enums import VacancyStatus
from ljpa_reworked.operations.resume_ops import reconstruct_resume_crewai
from ljpa_reworked.services.harness_runner import HarnessSubmitResult
from ljpa_reworked.workflow import save_resume


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def sample_resume_crewai() -> ResumeCrewAI:
    return ResumeCrewAI(
        personal_info=PersonalInfoCrewAI(
            name="John Doe",
            email="john@example.com",
            phone="123-456-7890",
            address="123 Main St",
            location="San Francisco, CA",
        ),
        summary="Experienced Software Engineer",
        education=[
            EducationCrewAI(
                course="BS Computer Science",
                institution="Tech University",
                location="CA",
                start_date="2016",
                end_date="2020",
            )
        ],
        experience=[
            ExperienceCrewAI(
                title="Software Engineer",
                company="Tech Co",
                location="CA",
                start_date="2020",
                end_date="Present",
                description=["Built scalable APIs", "Led team", "Optimized DB"],
            )
        ],
        skills=[SkillCrewAI(title="Python", elements=["FastAPI", "Pytest"])],
        projects=[
            ProjectCrewAI(
                title="Project A",
                description="Desc A",
                highlights=["H1", "H2", "H3"],
            )
        ],
        certifications=[CertificationCrewAI(title="AWS Certified")],
    )


def test_save_resume_persists_structured_data_only(db_session):
    vacancy = Vacancy(
        title="Python Engineer",
        text="Job details",
        submit_url="https://example.com/job/1",
        source="LinkedIn",
        visa_status="not_required",
    )
    db_session.add(vacancy)
    db_session.commit()

    resume_data = sample_resume_crewai()

    with patch(
        "ljpa_reworked.services.rendercv_helper.render_resume_crewai_to_pdf"
    ) as mock_render:
        saved = save_resume(resume_data, vacancy, db_session)

    mock_render.assert_not_called()
    assert saved.path is None
    assert saved.summary == "Experienced Software Engineer"
    assert saved.personal_info["name"] == "John Doe"


def test_reconstruct_resume_crewai(db_session):
    vacancy = Vacancy(
        title="Python Engineer",
        text="Job details",
        submit_url="https://example.com/job/1",
        source="LinkedIn",
        visa_status="not_required",
    )
    db_session.add(vacancy)
    db_session.commit()

    resume_data = sample_resume_crewai()
    saved = save_resume(resume_data, vacancy, db_session)

    reconstructed = reconstruct_resume_crewai(saved)
    assert isinstance(reconstructed, ResumeCrewAI)
    assert reconstructed.personal_info.name == "John Doe"
    assert len(reconstructed.experience) == 1
    assert reconstructed.experience[0].company == "Tech Co"


def test_submit_top_vacancies_renders_pdf_on_demand(db_session, tmp_path):
    vacancy = Vacancy(
        title="Python Engineer",
        text="Job details",
        submit_url="https://example.com/job/1",
        source="LinkedIn",
        visa_status="not_required",
        status=VacancyStatus.application_prepared,
    )
    db_session.add(vacancy)
    db_session.commit()
    db_session.add(
        BasicEvaluation(vacancy_id=vacancy.id, rating=90, summary="Good fit")
    )
    db_session.commit()
    resumes_dir = tmp_path / "resumes"
    saved = save_resume(sample_resume_crewai(), vacancy, db_session)
    assert saved.path is None

    def fake_render(resume, target_path):
        with open(target_path, "wb") as f:
            f.write(b"%PDF-1.4")
        return target_path

    with (
        patch("ljpa_reworked.main.SUBMISSION_RESUMES_DIR", str(resumes_dir)),
        patch("ljpa_reworked.main.get_gemini_quota_remaining", return_value=1.0),
        patch(
            "ljpa_reworked.main.render_resume_crewai_to_pdf", side_effect=fake_render
        ) as mock_render,
        patch(
            "ljpa_reworked.main.harness_submit",
            return_value=HarnessSubmitResult(
                completed=True, tail_lines=['{"status":"success"}\n']
            ),
        ) as harness,
        patch(
            "ljpa_reworked.main.crewai_review_submission_result",
            return_value=SubmissionReviewCrewAI(decision="success"),
        ),
    ):
        submit_top_vacancies(db_session)

    mock_render.assert_called_once()
    assert (
        harness.call_args.kwargs["resume_path"]
        == f"/inputs/resources/resumes/resume_{vacancy.id}.pdf"
    )
    assert vacancy.status == VacancyStatus.submitted_via_url
    assert saved.path == f"resume_{vacancy.id}.pdf"


def test_submit_top_vacancies_uses_persisted_pdf_without_rendering(
    db_session, tmp_path
):
    vacancy = Vacancy(
        title="Python Engineer",
        text="Job details",
        submit_url="https://example.com/job/1",
        source="LinkedIn",
        visa_status="not_required",
        status=VacancyStatus.application_prepared,
    )
    db_session.add(vacancy)
    db_session.commit()
    db_session.add(
        BasicEvaluation(vacancy_id=vacancy.id, rating=90, summary="Good fit")
    )
    db_session.commit()
    resumes_dir = tmp_path / "resumes"
    resumes_dir.mkdir()
    (resumes_dir / "resume.pdf").write_bytes(b"%PDF-1.4")
    saved = save_resume(sample_resume_crewai(), vacancy, db_session)
    saved.path = "resume.pdf"
    db_session.commit()
    with (
        patch("ljpa_reworked.main.SUBMISSION_RESUMES_DIR", str(resumes_dir)),
        patch("ljpa_reworked.main.get_gemini_quota_remaining", return_value=1.0),
        patch("ljpa_reworked.main.render_resume_crewai_to_pdf") as mock_render,
        patch(
            "ljpa_reworked.main.harness_submit",
            return_value=HarnessSubmitResult(
                completed=True, tail_lines=['{"status":"success"}\n']
            ),
        ) as harness,
        patch(
            "ljpa_reworked.main.crewai_review_submission_result",
            return_value=SubmissionReviewCrewAI(decision="success"),
        ),
    ):
        submit_top_vacancies(db_session)
    mock_render.assert_not_called()
    assert (
        harness.call_args.kwargs["resume_path"]
        == "/inputs/resources/resumes/resume.pdf"
    )
    assert vacancy.status == VacancyStatus.submitted_via_url


def test_submit_top_vacancies_marks_rendering_error_as_application_error(
    db_session, tmp_path
):
    vacancy = Vacancy(
        title="Python Engineer",
        text="Job details",
        submit_url="https://example.com/job/2",
        source="LinkedIn",
        visa_status="not_required",
        status=VacancyStatus.application_prepared,
    )
    db_session.add(vacancy)
    db_session.commit()
    db_session.add(
        BasicEvaluation(vacancy_id=vacancy.id, rating=90, summary="Good fit")
    )
    db_session.commit()
    save_resume(sample_resume_crewai(), vacancy, db_session)
    with (
        patch("ljpa_reworked.main.SUBMISSION_RESUMES_DIR", str(tmp_path / "resumes")),
        patch("ljpa_reworked.main.get_gemini_quota_remaining", return_value=1.0),
        patch(
            "ljpa_reworked.main.render_resume_crewai_to_pdf",
            side_effect=RuntimeError("Render error"),
        ),
    ):
        submit_top_vacancies(db_session)
    assert vacancy.status == VacancyStatus.application_error
