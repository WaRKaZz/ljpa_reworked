import os
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
)
from ljpa_reworked.models.database_models import BasicEvaluation, Vacancy
from ljpa_reworked.models.enums import VacancyStatus
from ljpa_reworked.operations.resume_ops import reconstruct_resume_crewai
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


def test_submit_top_vacancies_renders_temp_pdf_and_retains_on_success(
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

    eval_record = BasicEvaluation(vacancy_id=vacancy.id, rating=90, summary="Good fit")
    db_session.add(eval_record)
    db_session.commit()

    saved_resume = save_resume(sample_resume_crewai(), vacancy, db_session)
    assert saved_resume.path is None

    resumes_dir = tmp_path / "resumes"
    resumes_dir.mkdir()

    created_pdf_path = None

    def fake_render(resume_obj, pdf_path):
        nonlocal created_pdf_path
        created_pdf_path = pdf_path
        with open(pdf_path, "w") as f:
            f.write("PDF Content")

    with (
        patch("ljpa_reworked.main.RESOURCES_DIR", str(tmp_path)),
        patch("ljpa_reworked.main.get_gemini_quota_remaining", return_value=1.0),
        patch(
            "ljpa_reworked.main.render_resume_crewai_to_pdf", side_effect=fake_render
        ) as mock_render,
        patch("ljpa_reworked.main.harness_submit", return_value=0) as mock_harness,
    ):
        submit_top_vacancies(db_session)

    mock_render.assert_called_once()
    mock_harness.assert_called_once()
    harness_path = mock_harness.call_args.kwargs["resume_path"]
    assert harness_path.startswith("/inputs/resources/resumes/temp_resume_")

    assert created_pdf_path is not None
    assert os.path.exists(created_pdf_path)
    assert vacancy.status == VacancyStatus.submitted_via_url


def test_submit_top_vacancies_marks_application_error_and_cleans_up_on_harness_error(
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

    eval_record = BasicEvaluation(vacancy_id=vacancy.id, rating=90, summary="Good fit")
    db_session.add(eval_record)
    db_session.commit()

    save_resume(sample_resume_crewai(), vacancy, db_session)

    resumes_dir = tmp_path / "resumes"
    resumes_dir.mkdir()

    created_pdf_path = None

    def fake_render(resume_obj, pdf_path):
        nonlocal created_pdf_path
        created_pdf_path = pdf_path
        with open(pdf_path, "w") as f:
            f.write("PDF Content")

    with (
        patch("ljpa_reworked.main.RESOURCES_DIR", str(tmp_path)),
        patch("ljpa_reworked.main.get_gemini_quota_remaining", return_value=1.0),
        patch(
            "ljpa_reworked.main.render_resume_crewai_to_pdf", side_effect=fake_render
        ),
        patch("ljpa_reworked.main.harness_submit", return_value=1),
    ):
        submit_top_vacancies(db_session)

    assert created_pdf_path is not None
    assert not os.path.exists(created_pdf_path)
    assert vacancy.status == VacancyStatus.application_error


def test_submit_top_vacancies_marks_application_error_and_cleans_up_on_exception(
    db_session, tmp_path
):
    vacancy = Vacancy(
        title="Python Engineer",
        text="Job details",
        submit_url="https://example.com/job/3",
        source="LinkedIn",
        visa_status="not_required",
        status=VacancyStatus.application_prepared,
    )
    db_session.add(vacancy)
    db_session.commit()

    eval_record = BasicEvaluation(vacancy_id=vacancy.id, rating=90, summary="Good fit")
    db_session.add(eval_record)
    db_session.commit()

    save_resume(sample_resume_crewai(), vacancy, db_session)

    resumes_dir = tmp_path / "resumes"
    resumes_dir.mkdir()

    created_pdf_path = None

    def fake_render(resume_obj, pdf_path):
        nonlocal created_pdf_path
        created_pdf_path = pdf_path
        with open(pdf_path, "w") as f:
            f.write("PDF Content")

    with (
        patch("ljpa_reworked.main.RESOURCES_DIR", str(tmp_path)),
        patch("ljpa_reworked.main.get_gemini_quota_remaining", return_value=1.0),
        patch(
            "ljpa_reworked.main.render_resume_crewai_to_pdf", side_effect=fake_render
        ),
        patch(
            "ljpa_reworked.main.harness_submit",
            side_effect=RuntimeError("Network timeout"),
        ),
    ):
        submit_top_vacancies(db_session)

    assert created_pdf_path is not None
    assert not os.path.exists(created_pdf_path)
    assert vacancy.status == VacancyStatus.application_error
