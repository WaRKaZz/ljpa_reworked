import json

from crewai.tasks.task_output import TaskOutput


def test_guardrail_normalizes_category_skills_and_long_summary():
    from ljpa_reworked.crews.resume_generation_crew.resume_generation_crew import (
        resume_output_guardrail,
    )

    raw = {
        "personal_info": {"name": "A", "email": "a@example.com", "phone": "1", "address": "A", "location": "A"},
        "summary": "S" * 501,
        "education": [],
        "experience": [],
        "skills": [{"category": "PLC", "items": ["TIA Portal", "WinCC"]}],
        "projects": [],
    }

    allowed, normalized = resume_output_guardrail(
        TaskOutput(description="resume", raw=json.dumps(raw), agent="resume_agent")
    )

    assert allowed
    payload = json.loads(normalized)
    assert payload["summary"] == "S" * 500
    assert payload["skills"] == [{"title": "PLC", "elements": ["TIA Portal", "WinCC"]}]
