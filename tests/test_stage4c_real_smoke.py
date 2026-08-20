import os
import time
from pathlib import Path

import pytest

from ljpa_reworked.crews.resume_evaluation_crew.resume_evaluation_crew import (
    ResumeEvaluationCrew,
)
from ljpa_reworked.models.crewai_pydantic_models import (
    BasicEvaluationCrewAI,
    ResumeCrewAI,
)


@pytest.mark.timeout(180)
def test_stage4c_real_smoke_evaluator_generator_render():
    """Real smoke end-to-end test: evaluator then generator using resources/profile.md and synthetic vacancy.

    Renders generated ResumeCrewAI to disposable PDF under /tmp, verifies non-zero size, and cleans up.
    Does not print profile, raw output, secrets, or PDF text.
    """
    # The production path requires canonical static-profile headings and fields.
    synthetic_profile = (
        Path(__file__).resolve().parents[1] / "resources" / "profile.md"
    ).read_text(encoding="utf-8")

    synthetic_inputs = {
        "title": "Senior Python Backend Engineer",
        "text": (
            "We are looking for a Senior Python Backend Engineer to build scalable microservices using Python, "
            "FastAPI, and PostgreSQL. Requirements: 5+ years experience with Python, async programming, Docker, and CI/CD."
        ),
        "submit_email": "jobs@example.com",
        "submit_url": "https://example.com/careers/python-engineer",
        "linkedin_url": "https://linkedin.com/in/testcandidate",
        "candidate_profile": synthetic_profile,
        "visa_status": "not_mentioned",
        "visa_status_context": "Visa status is not specified in the database (database visa_status: not_mentioned). Evaluate feasibility based on vacancy text and secondary factors.",
    }

    start_eval = time.monotonic()
    eval_crew_instance = ResumeEvaluationCrew()
    eval_result = eval_crew_instance.crew().kickoff(inputs=synthetic_inputs)
    eval_time = time.monotonic() - start_eval

    assert len(eval_result.tasks_output) > 0
    from ljpa_reworked.crew_workflow import extract_clean_json

    merged_data = {}
    for task_out in eval_result.tasks_output:
        data = extract_clean_json(task_out.raw)
        if isinstance(data, dict):
            merged_data.update(data)
    if "visa_probability" not in merged_data:
        merged_data["visa_probability"] = 100
    if "missing_mandatory_facts" not in merged_data:
        merged_data["missing_mandatory_facts"] = []

    eval_pydantic = BasicEvaluationCrewAI.model_validate(merged_data)
    assert isinstance(eval_pydantic, BasicEvaluationCrewAI)
    assert 0 <= eval_pydantic.rating <= 100
    assert bool(eval_pydantic.summary)
    assert 0 <= eval_pydantic.visa_probability <= 100
    assert eval_time < 90.0, f"Evaluator took too long: {eval_time:.2f}s"
    # crewai_evaluate_vacancy clears vacancy-fit gaps after profile completeness passes.
    eval_pydantic = eval_pydantic.model_copy(update={"missing_mandatory_facts": []})

    from unittest.mock import MagicMock, patch

    from ljpa_reworked.crew_workflow import crewai_generate_resume_with_retry

    mock_vacancy = MagicMock()
    mock_vacancy.title = synthetic_inputs["title"]
    mock_vacancy.text = synthetic_inputs["text"]
    mock_vacancy.submit_email = synthetic_inputs["submit_email"]
    mock_vacancy.submit_url = synthetic_inputs["submit_url"]

    start_gen = time.monotonic()
    with patch(
        "ljpa_reworked.crew_workflow.read_profile_text", return_value=synthetic_profile
    ):
        resume_pydantic, out_pdf = crewai_generate_resume_with_retry(
            mock_vacancy, eval_pydantic
        )
    gen_time = time.monotonic() - start_gen

    assert isinstance(resume_pydantic, ResumeCrewAI)
    assert bool(resume_pydantic.personal_info.name)
    assert len(resume_pydantic.experience) > 0
    assert gen_time < 180.0, f"Generator took too long: {gen_time:.2f}s"

    try:
        assert os.path.exists(out_pdf), "PDF file does not exist after rendering"
        assert os.path.getsize(out_pdf) > 0, "PDF file is empty (0 bytes)"
    finally:
        if os.path.exists(out_pdf):
            os.remove(out_pdf)
            assert not os.path.exists(out_pdf), (
                "PDF file failed to delete after smoke verification"
            )
