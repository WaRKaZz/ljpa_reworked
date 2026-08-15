from unittest.mock import MagicMock, patch

from ljpa_reworked.crew_workflow import crewai_generate_resume_with_retry
from ljpa_reworked.models.crewai_pydantic_models import BasicEvaluationCrewAI
from ljpa_reworked.services.rendercv_helper import ResumeLayoutError


def test_resume_retry_defaults_to_three_layout_corrections():
    resume = MagicMock()
    resume.model_dump.return_value = {"summary": "resume"}
    vacancy = MagicMock()
    evaluation = BasicEvaluationCrewAI(summary="fit", rating=80)
    calls = []

    def generate(**kwargs):
        calls.append(kwargs)
        return resume

    def render(_resume, _path):
        if len(calls) < 4:
            raise ResumeLayoutError(
                "RenderCV output failed page layout validation: page is blank"
            )

    with (
        patch(
            "ljpa_reworked.crew_workflow.crewai_generate_resume", side_effect=generate
        ),
        patch(
            "ljpa_reworked.crew_workflow.render_resume_crewai_to_pdf",
            side_effect=render,
        ),
    ):
        crewai_generate_resume_with_retry(vacancy, evaluation)

    assert len(calls) == 4
    assert calls[-1]["layout_feedback"]
    assert calls[-1]["prior_resume_json"]


def test_resume_retry_does_not_retry_gateway_errors_as_layout_errors():
    vacancy = MagicMock()
    evaluation = BasicEvaluationCrewAI(summary="fit", rating=80)
    with patch(
        "ljpa_reworked.crew_workflow.crewai_generate_resume",
        side_effect=RuntimeError("gateway unavailable"),
    ) as generate:
        import pytest

        with pytest.raises(RuntimeError, match="gateway unavailable"):
            crewai_generate_resume_with_retry(vacancy, evaluation)
    generate.assert_called_once()
