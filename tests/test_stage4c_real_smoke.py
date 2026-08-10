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
    synthetic_inputs = {
        "title": "Senior Python Backend Engineer",
        "text": (
            "We are looking for a Senior Python Backend Engineer to build scalable microservices using Python, "
            "FastAPI, and PostgreSQL. Requirements: 5+ years experience with Python, async programming, Docker, and CI/CD."
        ),
        "submit_email": "jobs@example.com",
        "submit_url": "https://example.com/careers/python-engineer",
        "linkedin_url": "https://linkedin.com/in/testcandidate",
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

    gen_inputs = {
        **synthetic_inputs,
        "rating": eval_pydantic.rating,
        "summary": eval_pydantic.summary,
    }

    start_gen = time.monotonic()
    gen_crew_instance = ResumeGenerationCrew()
    gen_result = gen_crew_instance.crew().kickoff(inputs=gen_inputs)
    gen_time = time.monotonic() - start_gen

    assert len(gen_result.tasks_output) > 0
    resume_pydantic = gen_result.tasks_output[0].pydantic
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
