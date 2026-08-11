from unittest.mock import MagicMock, patch

import pytest

from ljpa_reworked.crew_workflow import crewai_generate_resume_with_retry
from ljpa_reworked.models.crewai_pydantic_models import (
    BasicEvaluationCrewAI,
    EducationCrewAI,
    ExperienceCrewAI,
    PersonalInfoCrewAI,
    ResumeCrewAI,
    SkillCrewAI,
)


def _make_dummy_resume() -> ResumeCrewAI:
    return ResumeCrewAI(
        personal_info=PersonalInfoCrewAI(
            name="John Doe",
            email="john@example.com",
            phone="+1 555-0199",
            address="123 Main St",
            location="New York, NY",
            target_title="Software Engineer",
        ),
        summary="Test summary",
        education=[
            EducationCrewAI(
                course="B.S. Computer Science",
                institution="University",
                location="City, ST",
                start_date="2016",
                end_date="2020",
            )
        ],
        experience=[
            ExperienceCrewAI(
                title="Engineer",
                company="Tech Co",
                location="City, ST",
                start_date="2020",
                end_date="Present",
                description=["Bullet 1", "Bullet 2", "Bullet 3"],
            )
        ],
        skills=[SkillCrewAI(title="Languages", elements=["Python", "Go"])],
    )


def test_retry_orchestration_first_candidate_valid():
    mock_vacancy = MagicMock()
    mock_eval = MagicMock(spec=BasicEvaluationCrewAI)
    dummy_resume = _make_dummy_resume()

    def mock_render(resume, path):
        return path

    with (
        patch(
            "ljpa_reworked.crew_workflow.crewai_generate_resume",
            return_value=dummy_resume,
        ) as mock_gen,
        patch(
            "ljpa_reworked.crew_workflow.render_resume_crewai_to_pdf",
            side_effect=mock_render,
        ) as mock_render_stub,
    ):
        resume, pdf_path = crewai_generate_resume_with_retry(mock_vacancy, mock_eval)

        assert resume == dummy_resume
        assert pdf_path.endswith(".pdf")
        assert mock_gen.call_count == 1
        assert mock_gen.call_args.kwargs.get("layout_feedback") == ""
        assert mock_render_stub.call_count == 1


def test_retry_orchestration_first_fails_layout_second_succeeds():
    mock_vacancy = MagicMock()
    mock_eval = MagicMock(spec=BasicEvaluationCrewAI)
    resume1 = _make_dummy_resume()
    resume2 = _make_dummy_resume()

    layout_err_msg = (
        "RenderCV output failed page layout validation: "
        "Page 1 (non-final) character count (2827) is outside required range [3300, 3475]"
    )

    def mock_render(resume, path):
        if mock_render.call_count == 1:
            raise RuntimeError(layout_err_msg)
        return path

    mock_render.call_count = 0

    def mock_render_wrapper(resume, path):
        mock_render.call_count += 1
        return mock_render(resume, path)

    with (
        patch(
            "ljpa_reworked.crew_workflow.crewai_generate_resume",
            side_effect=[resume1, resume2],
        ) as mock_gen,
        patch(
            "ljpa_reworked.crew_workflow.render_resume_crewai_to_pdf",
            side_effect=mock_render_wrapper,
        ),
    ):
        resume, pdf_path = crewai_generate_resume_with_retry(mock_vacancy, mock_eval)

        assert resume == resume2
        assert pdf_path.endswith(".pdf")
        assert mock_gen.call_count == 2
        call2_kwargs = mock_gen.call_args_list[1].kwargs
        assert layout_err_msg in call2_kwargs.get("layout_feedback", "")


def test_retry_orchestration_both_fail_cleans_files_and_raises(tmp_path):
    mock_vacancy = MagicMock()
    mock_eval = MagicMock(spec=BasicEvaluationCrewAI)
    resume1 = _make_dummy_resume()
    resume2 = _make_dummy_resume()

    layout_err_msg = "RenderCV output failed page layout validation: Page 1 short"
    temp_pdf_created = tmp_path / "temp_fail.pdf"

    def mock_render_side_effect(resume, path):
        # Create a temp file to test cleanup
        temp_pdf_created.write_text("dummy pdf content")
        raise RuntimeError(layout_err_msg)

    with (
        patch(
            "ljpa_reworked.crew_workflow.crewai_generate_resume",
            side_effect=[resume1, resume2],
        ) as mock_gen,
        patch(
            "ljpa_reworked.crew_workflow.render_resume_crewai_to_pdf",
            side_effect=mock_render_side_effect,
        ),
    ):
        with pytest.raises(RuntimeError) as exc_info:
            crewai_generate_resume_with_retry(mock_vacancy, mock_eval)

        assert layout_err_msg in str(exc_info.value)
        assert mock_gen.call_count == 2


def test_save_resume_with_pre_rendered_temp_pdf(tmp_path):
    from ljpa_reworked.models.database_models import Vacancy
    from ljpa_reworked.workflow import save_resume

    db = MagicMock()
    mock_vacancy = MagicMock(spec=Vacancy)
    mock_vacancy.id = 42

    dummy_resume = _make_dummy_resume()
    temp_pdf = tmp_path / "pre_rendered.pdf"
    temp_pdf.write_bytes(b"%PDF-1.4 dummy content")

    with (
        patch("ljpa_reworked.workflow.render_resume_crewai_to_pdf") as mock_render,
        patch(
            "ljpa_reworked.workflow.create_resume",
            return_value=MagicMock(path="resume_42_abc.pdf"),
        ) as mock_create_resume,
    ):
        orm_resume = save_resume(
            dummy_resume, mock_vacancy, db, temp_pdf_path=str(temp_pdf)
        )

        assert orm_resume.path == "resume_42_abc.pdf"
        assert mock_render.call_count == 0  # Should NOT render a 3rd time
        assert mock_create_resume.call_count == 1
        assert not temp_pdf.exists()  # Temp PDF should be cleaned up after saving


def test_format_numeric_layout_feedback_branches():
    from ljpa_reworked.crew_workflow import _format_numeric_layout_feedback

    err_short = "Page 1 (non-final) character count (2800) is outside required range [3300, 3475]"
    res_short = _format_numeric_layout_feedback(err_short)
    assert "expand the resume text by approximately 587 characters" in res_short

    err_long = "Page 1 (non-final) character count (3600) is outside required range [3300, 3475]"
    res_long = _format_numeric_layout_feedback(err_long)
    assert "trim the resume text by approximately 213 characters" in res_long

    err_final = "Page 2 (final) character count (1200) is less than minimum 1400 characters"
    res_final = _format_numeric_layout_feedback(err_final)
    assert "add approximately 300 characters" in res_final

    err_other = "Some generic error"
    assert _format_numeric_layout_feedback(err_other) == err_other


def test_save_resume_cleans_up_on_create_resume_error(tmp_path):
    from ljpa_reworked.models.database_models import Vacancy
    from ljpa_reworked.workflow import save_resume

    db = MagicMock()
    mock_vacancy = MagicMock(spec=Vacancy)
    mock_vacancy.id = 99

    dummy_resume = _make_dummy_resume()
    temp_pdf = tmp_path / "pre_rendered_db_fail.pdf"
    temp_pdf.write_bytes(b"%PDF-1.4 dummy content")

    with patch(
        "ljpa_reworked.workflow.create_resume", side_effect=RuntimeError("DB fail")
    ):
        with pytest.raises(RuntimeError) as exc_info:
            save_resume(dummy_resume, mock_vacancy, db, temp_pdf_path=str(temp_pdf))

        assert "DB fail" in str(exc_info.value)
        assert not temp_pdf.exists()


def test_save_resume_and_retry_oserror_cleanup_branches():
    from ljpa_reworked.models.database_models import Vacancy
    from ljpa_reworked.workflow import save_resume

    db = MagicMock()
    mock_vacancy = MagicMock(spec=Vacancy)
    mock_vacancy.id = 99
    dummy_resume = _make_dummy_resume()

    with patch("shutil.copy", side_effect=RuntimeError("copy error")):
        with patch("os.path.exists", return_value=True):
            with patch("os.remove", side_effect=OSError("remove error")):
                with pytest.raises(RuntimeError) as exc_info:
                    save_resume(dummy_resume, mock_vacancy, db, temp_pdf_path="/tmp/fake.pdf")
                assert "copy error" in str(exc_info.value)

    with (
        patch("ljpa_reworked.crew_workflow.crewai_generate_resume", return_value=dummy_resume),
        patch("ljpa_reworked.crew_workflow.render_resume_crewai_to_pdf", side_effect=RuntimeError("render fail")),
        patch("os.path.exists", return_value=True),
        patch("os.remove", side_effect=OSError("remove fail")),
    ):
        with pytest.raises(RuntimeError) as exc_info:
            crewai_generate_resume_with_retry(mock_vacancy, MagicMock())
        assert "render fail" in str(exc_info.value)


def test_render_resume_crewai_to_pdf_layout_validation_oserror_handling(tmp_path):
    from ljpa_reworked.services.rendercv_helper import render_resume_crewai_to_pdf

    dummy_resume = _make_dummy_resume()
    out_pdf = tmp_path / "layout_fail.pdf"

    with patch(
        "ljpa_reworked.services.rendercv_helper.convert_resume_crewai_to_rendercv_input",
        return_value={},
    ):
        with patch("subprocess.run", return_value=MagicMock(returncode=0)):
            with patch("os.path.exists", return_value=True):
                with patch(
                    "ljpa_reworked.services.rendercv_helper.validate_pdf_page_layout",
                    return_value=(False, "Page 1 layout error"),
                ):
                    with patch("os.remove", side_effect=OSError("remove error")):
                        with pytest.raises(RuntimeError) as exc_info:
                            render_resume_crewai_to_pdf(dummy_resume, str(out_pdf))
                        assert "Page 1 layout error" in str(exc_info.value)
