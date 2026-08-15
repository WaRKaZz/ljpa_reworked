from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from ljpa_reworked.crew_workflow import crewai_review_submission_result
from ljpa_reworked.models.crewai_pydantic_models import SubmissionReviewCrewAI


def test_submission_review_pydantic_model():
    success = SubmissionReviewCrewAI(decision="success")
    assert success.decision == "success"
    assert success.error_description is None

    err = SubmissionReviewCrewAI(
        decision="error", error_description="Form submission failed"
    )
    assert err.decision == "error"
    assert err.error_description == "Form submission failed"

    with pytest.raises(ValidationError):
        SubmissionReviewCrewAI(decision="invalid_choice")  # type: ignore


def test_submission_review_crew_class():
    from ljpa_reworked.crews.submission_review_crew import SubmissionReviewCrew

    crew_obj = SubmissionReviewCrew()
    crew_instance = crew_obj.crew()
    assert crew_instance is not None
    assert len(crew_obj.agents) == 1
    assert len(crew_obj.tasks) == 1
    assert crew_obj.tasks[0].output_pydantic == SubmissionReviewCrewAI


def test_crewai_review_submission_result_success():
    mock_crew = MagicMock()
    mock_output = MagicMock()
    mock_output.tasks_output = [
        MagicMock(pydantic=SubmissionReviewCrewAI(decision="success"))
    ]
    mock_crew.kickoff.return_value = mock_output

    tail_lines = [
        '{"event": "step", "content": "form submitted"}\n',
        '{"event": "result", "result": {"status": "SUCCESS"}}\n',
    ]

    with patch(
        "ljpa_reworked.crew_workflow.create_review_crew", return_value=mock_crew
    ) as mock_create:
        review = crewai_review_submission_result(tail_lines)

    assert review.decision == "success"
    assert review.error_description is None
    mock_create.assert_called_once()
    mock_crew.kickoff.assert_called_once()
    inputs = mock_crew.kickoff.call_args.kwargs["inputs"]
    assert "stream_tail" in inputs
    assert "form submitted" in inputs["stream_tail"]
    assert "conversation_id" not in inputs["stream_tail"]


def test_crewai_review_submission_result_error_description():
    mock_crew = MagicMock()
    mock_output = MagicMock()
    mock_output.tasks_output = [
        MagicMock(
            pydantic=SubmissionReviewCrewAI(
                decision="error", error_description="CAPTCHA blocking submit"
            )
        )
    ]
    mock_crew.kickoff.return_value = mock_output

    with patch(
        "ljpa_reworked.crew_workflow.create_review_crew", return_value=mock_crew
    ):
        review = crewai_review_submission_result(
            ['{"event": "error", "content": "CAPTCHA found"}\n']
        )

    assert review.decision == "error"
    assert review.error_description == "CAPTCHA blocking submit"


def test_crewai_review_submission_result_malformed_output_becomes_error():
    mock_crew = MagicMock()
    mock_crew.kickoff.side_effect = RuntimeError("CrewAI API connection failed")

    with patch(
        "ljpa_reworked.crew_workflow.create_review_crew", return_value=mock_crew
    ):
        review = crewai_review_submission_result(["invalid tail line\n"])

    assert review.decision == "error"
    assert "CrewAI API connection failed" in (review.error_description or "")


def test_orchestration_review_error_transitions_to_application_error_and_notifies_telegram():
    from ljpa_reworked.main import submit_top_vacancies
    from ljpa_reworked.models.enums import VacancyStatus
    from ljpa_reworked.services.harness_runner import HarnessSubmitResult

    mock_db = MagicMock()
    mock_vacancy = MagicMock(id=42, title="Python Dev", submit_url="https://example.com/job")
    mock_vacancy.status = VacancyStatus.application_prepared
    mock_ranked = MagicMock(vacancy=mock_vacancy)
    mock_resume = MagicMock(path="resume_42.pdf")

    with (
        patch("ljpa_reworked.main.build_ranked_submission_queue", return_value=[mock_ranked]),
        patch("ljpa_reworked.main.get_gemini_quota_remaining", return_value=0.5),
        patch("ljpa_reworked.main.get_resume_by_vacancy", return_value=mock_resume),
        patch("os.path.isfile", return_value=True),
        patch("ljpa_reworked.main.harness_submit") as mock_submit,
        patch("ljpa_reworked.main.crewai_review_submission_result") as mock_review,
        patch("ljpa_reworked.main.transition_vacancy_status") as mock_transition,
        patch("ljpa_reworked.main.Telegram") as mock_telegram_cls,
        patch("ljpa_reworked.main.harness_save_site_skill") as mock_save_skill,
    ):
        mock_submit.return_value = HarnessSubmitResult(
            completed=True,
            conversation_id="conv-999",
            tail_lines=["line1\n", "line2\n"],
        )
        mock_review.return_value = SubmissionReviewCrewAI(
            decision="error", error_description="Submit button was missing"
        )
        mock_telegram_instance = MagicMock()
        mock_telegram_cls.return_value = mock_telegram_instance

        ret = submit_top_vacancies(mock_db)
        assert ret == 0

        mock_submit.assert_called_once()
        mock_review.assert_called_once_with(["line1\n", "line2\n"])
        mock_transition.assert_called_once_with(
            mock_db, 42, VacancyStatus.application_error
        )
        mock_telegram_instance.send_message.assert_called_once()
        msg = mock_telegram_instance.send_message.call_args.args[0]
        assert "42" in msg
        assert "Submit button was missing" in msg
        mock_save_skill.assert_not_called()


def test_orchestration_review_success_transitions_to_submitted_via_url_and_runs_second_pass():
    from ljpa_reworked.main import submit_top_vacancies
    from ljpa_reworked.services.harness_runner import HarnessSubmitResult

    mock_db = MagicMock()
    mock_vacancy = MagicMock(id=101, title="Backend Dev", submit_url="https://example.com/job101")
    mock_ranked = MagicMock(vacancy=mock_vacancy)
    mock_resume = MagicMock(path="resume_101.pdf")

    call_order = []

    def mock_confirm(db, vacancy_id):
        call_order.append("confirm_submitted")

    def mock_save_skill(conversation_id, **kwargs):
        call_order.append(f"save_skill_{conversation_id}")
        return 0

    with (
        patch("ljpa_reworked.main.build_ranked_submission_queue", return_value=[mock_ranked]),
        patch("ljpa_reworked.main.get_gemini_quota_remaining", return_value=0.5),
        patch("ljpa_reworked.main.get_resume_by_vacancy", return_value=mock_resume),
        patch("os.path.isfile", return_value=True),
        patch("ljpa_reworked.main.harness_submit") as mock_submit,
        patch("ljpa_reworked.main.crewai_review_submission_result") as mock_review,
        patch("ljpa_reworked.main.confirm_url_application_submitted", side_effect=mock_confirm),
        patch("ljpa_reworked.main.harness_save_site_skill", side_effect=mock_save_skill),
        patch("ljpa_reworked.main.Telegram") as mock_telegram_cls,
    ):
        mock_submit.return_value = HarnessSubmitResult(
            completed=True,
            conversation_id="conv-cid-101",
            tail_lines=["done\n"],
        )
        mock_review.return_value = SubmissionReviewCrewAI(decision="success")

        ret = submit_top_vacancies(mock_db)
        assert ret == 0

        assert call_order == ["confirm_submitted", "save_skill_conv-cid-101"]
        mock_telegram_cls.return_value.send_message.assert_not_called()


def test_orchestration_second_pass_timeout_or_exception_preserves_submitted_via_url_and_notifies_telegram():
    from ljpa_reworked.main import submit_top_vacancies
    from ljpa_reworked.services.harness_runner import HarnessSubmitResult

    mock_db = MagicMock()
    mock_vacancy = MagicMock(id=202, title="Lead Engineer", submit_url="https://example.com/job202")
    mock_ranked = MagicMock(vacancy=mock_vacancy)
    mock_resume = MagicMock(path="resume_202.pdf")

    with (
        patch("ljpa_reworked.main.build_ranked_submission_queue", return_value=[mock_ranked]),
        patch("ljpa_reworked.main.get_gemini_quota_remaining", return_value=0.5),
        patch("ljpa_reworked.main.get_resume_by_vacancy", return_value=mock_resume),
        patch("os.path.isfile", return_value=True),
        patch("ljpa_reworked.main.harness_submit") as mock_submit,
        patch("ljpa_reworked.main.crewai_review_submission_result") as mock_review,
        patch("ljpa_reworked.main.confirm_url_application_submitted") as mock_confirm,
        patch("ljpa_reworked.main.harness_save_site_skill", side_effect=RuntimeError("Skill save timeout")),
        patch("ljpa_reworked.main.transition_vacancy_status") as mock_transition,
        patch("ljpa_reworked.main.Telegram") as mock_telegram_cls,
    ):
        mock_submit.return_value = HarnessSubmitResult(
            completed=True,
            conversation_id="conv-cid-202",
            tail_lines=["submitted\n"],
        )
        mock_review.return_value = SubmissionReviewCrewAI(decision="success")
        mock_telegram_instance = MagicMock()
        mock_telegram_cls.return_value = mock_telegram_instance

        ret = submit_top_vacancies(mock_db)
        assert ret == 0

        mock_confirm.assert_called_once_with(db=mock_db, vacancy_id=202)
        mock_transition.assert_not_called()
        mock_telegram_instance.send_message.assert_called_once()
        msg = mock_telegram_instance.send_message.call_args.args[0]
        assert "202" in msg
        assert "Skill saving failed" in msg


def test_orchestration_runs_crewai_review_on_stream_tail_when_terminal_flag_is_error():
    from ljpa_reworked.main import submit_top_vacancies
    from ljpa_reworked.models.crewai_pydantic_models import SubmissionReviewCrewAI
    from ljpa_reworked.services.harness_runner import HarnessSubmitResult

    mock_db = MagicMock()
    mock_vacancy = MagicMock(id=303, title="Data Engineer", submit_url="https://example.com/job303")
    mock_ranked = MagicMock(vacancy=mock_vacancy)
    mock_resume = MagicMock(path="resume_303.pdf")

    with (
        patch("ljpa_reworked.main.build_ranked_submission_queue", return_value=[mock_ranked]),
        patch("ljpa_reworked.main.get_gemini_quota_remaining", return_value=0.5),
        patch("ljpa_reworked.main.get_resume_by_vacancy", return_value=mock_resume),
        patch("os.path.isfile", return_value=True),
        patch("ljpa_reworked.main.harness_submit") as mock_submit,
        patch("ljpa_reworked.main.crewai_review_submission_result") as mock_review,
        patch("ljpa_reworked.main.confirm_url_application_submitted") as mock_confirm,
        patch("ljpa_reworked.main.harness_save_site_skill"),
        patch("ljpa_reworked.main.Telegram"),
    ):
        mock_submit.return_value = HarnessSubmitResult(
            completed=False,
            conversation_id="conv-303",
            tail_lines=['{"event":"step","content":"ATS confirmation visible"}\n'],
        )
        mock_review.return_value = SubmissionReviewCrewAI(decision="success")

        ret = submit_top_vacancies(mock_db)
        assert ret == 0

        mock_review.assert_called_once_with(['{"event":"step","content":"ATS confirmation visible"}\n'])
        mock_confirm.assert_called_once_with(db=mock_db, vacancy_id=303)


def test_orchestration_no_stream_evidence_skips_review_transitions_to_application_error_and_notifies_telegram():
    from ljpa_reworked.main import submit_top_vacancies
    from ljpa_reworked.models.enums import VacancyStatus
    from ljpa_reworked.services.harness_runner import HarnessSubmitResult

    mock_db = MagicMock()
    mock_vacancy = MagicMock(id=404, title="QA Engineer", submit_url="https://example.com/job404")
    mock_ranked = MagicMock(vacancy=mock_vacancy)
    mock_resume = MagicMock(path="resume_404.pdf")

    with (
        patch("ljpa_reworked.main.build_ranked_submission_queue", return_value=[mock_ranked]),
        patch("ljpa_reworked.main.get_gemini_quota_remaining", return_value=0.5),
        patch("ljpa_reworked.main.get_resume_by_vacancy", return_value=mock_resume),
        patch("os.path.isfile", return_value=True),
        patch("ljpa_reworked.main.harness_submit") as mock_submit,
        patch("ljpa_reworked.main.crewai_review_submission_result") as mock_review,
        patch("ljpa_reworked.main.transition_vacancy_status") as mock_transition,
        patch("ljpa_reworked.main.Telegram") as mock_telegram_cls,
    ):
        mock_submit.return_value = HarnessSubmitResult(
            completed=False,
            conversation_id=None,
            tail_lines=[],
        )
        mock_telegram_instance = MagicMock()
        mock_telegram_cls.return_value = mock_telegram_instance

        ret = submit_top_vacancies(mock_db)
        assert ret == 0

        mock_review.assert_not_called()
        mock_transition.assert_called_once_with(mock_db, 404, VacancyStatus.application_error)
        mock_telegram_instance.send_message.assert_called_once()
        msg = mock_telegram_instance.send_message.call_args.args[0]
        assert "404" in msg
