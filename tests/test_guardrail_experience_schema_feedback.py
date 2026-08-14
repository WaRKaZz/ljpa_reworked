import json

from crewai.tasks.task_output import TaskOutput


def test_guardrail_returns_exact_required_experience_fields_before_pydantic():
    from ljpa_reworked.crews.resume_generation_crew.resume_generation_crew import (
        resume_output_guardrail,
    )

    raw = {
        "personal_info": {
            "name": "A",
            "email": "a@example.com",
            "phone": "1",
            "address": "A",
            "location": "A",
        },
        "summary": "Automation engineer",
        "education": [],
        "experience": [
            {
                "company": "TCO",
                "location": "Tengiz",
                "description": ["One", "Two", "Three"],
            }
        ],
        "skills": [],
        "projects": [],
    }

    allowed, feedback = resume_output_guardrail(
        TaskOutput(description="resume", raw=json.dumps(raw), agent="resume_agent")
    )

    assert not allowed
    assert "experience[0]" in feedback
    assert '"title"' in feedback
    assert '"start_date"' in feedback
    assert '"end_date"' in feedback
    assert "Return only the complete JSON object" in feedback
