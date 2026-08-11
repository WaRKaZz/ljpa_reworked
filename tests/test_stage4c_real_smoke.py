import os
import time

import pytest

from ljpa_reworked.crews.resume_evaluation_crew.resume_evaluation_crew import (
    ResumeEvaluationCrew,
)
from ljpa_reworked.crews.resume_generation_crew.resume_generation_crew import (
    ResumeGenerationCrew,
)
from ljpa_reworked.models.crewai_pydantic_models import (
    BasicEvaluationCrewAI,
    ResumeCrewAI,
)
from ljpa_reworked.services.rendercv_helper import (
    render_resume_crewai_to_pdf,
)


@pytest.mark.timeout(180)
def test_stage4c_real_smoke_evaluator_generator_render():
    """Real smoke end-to-end test: evaluator then generator using resources/profile.md and synthetic vacancy.

    Renders generated ResumeCrewAI to disposable PDF under /tmp, verifies non-zero size, and cleans up.
    Does not print profile, raw output, secrets, or PDF text.
    """
    synthetic_profile = (
        "## General Information\nName: Test Candidate\nEmail: candidate@example.com\nPhone: +1 555-0100\nLocation: NY\n"
        "## Summary\nExperienced Python Backend Engineer with microservices background.\n"
        "## Experience\n- Role: Senior Developer at Tech Corp (2020-Present)\n  Highlights: Built FastAPI microservices, optimized queries, Docker deployment.\n"
        "## Education\n- BS CS, Tech University (2016-2020)\n"
        "## Skills\n- Python, FastAPI, PostgreSQL, Docker, CI/CD"
    )

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
    }

    start_eval = time.monotonic()
    eval_crew_instance = ResumeEvaluationCrew()
    eval_result = eval_crew_instance.crew().kickoff(inputs=synthetic_inputs)
    eval_time = time.monotonic() - start_eval

    assert len(eval_result.tasks_output) > 0
    eval_pydantic = eval_result.tasks_output[0].pydantic
    assert isinstance(eval_pydantic, BasicEvaluationCrewAI)
    assert 0 <= eval_pydantic.rating <= 100
    assert bool(eval_pydantic.summary)
    assert eval_time < 90.0, f"Evaluator took too long: {eval_time:.2f}s"

    from unittest.mock import MagicMock, patch
    from ljpa_reworked.crew_workflow import crewai_generate_resume

    mock_vacancy = MagicMock()
    mock_vacancy.title = synthetic_inputs["title"]
    mock_vacancy.text = synthetic_inputs["text"]
    mock_vacancy.submit_email = synthetic_inputs["submit_email"]
    mock_vacancy.submit_url = synthetic_inputs["submit_url"]

    start_gen = time.monotonic()
    with patch("ljpa_reworked.crew_workflow.read_profile_text", return_value=synthetic_profile):
        resume_pydantic = crewai_generate_resume(mock_vacancy, eval_pydantic)
    gen_time = time.monotonic() - start_gen

    assert isinstance(resume_pydantic, ResumeCrewAI)
    assert bool(resume_pydantic.personal_info.name)
    assert len(resume_pydantic.experience) > 0
    assert gen_time < 90.0, f"Generator took too long: {gen_time:.2f}s"

    out_pdf = f"/tmp/stage4c_smoke_resume_{int(time.time())}.pdf"
    if os.path.exists(out_pdf):
        os.remove(out_pdf)

    try:
        pdf_path = render_resume_crewai_to_pdf(resume_pydantic, out_pdf)
        assert pdf_path == out_pdf
        assert os.path.exists(out_pdf), "PDF file does not exist after rendering"
        assert os.path.getsize(out_pdf) > 0, "PDF file is empty (0 bytes)"
    finally:
        if os.path.exists(out_pdf):
            os.remove(out_pdf)
            assert not os.path.exists(out_pdf), "PDF file failed to delete after smoke verification"
