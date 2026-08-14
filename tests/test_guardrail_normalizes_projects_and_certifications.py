import json

from crewai.tasks.task_output import TaskOutput


def test_guardrail_normalizes_missing_project_description_and_certification_strings():
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
        "experience": [],
        "skills": [],
        "projects": [
            {
                "title": "Water Supply Automation",
                "highlights": ["Scope", "Implementation", "Outcome"],
            }
        ],
        "certifications": ["Siemens — SIMATIC S7 Programming, 2022"],
    }

    allowed, normalized = resume_output_guardrail(
        TaskOutput(description="resume", raw=json.dumps(raw), agent="resume_agent")
    )

    assert allowed
    payload = json.loads(normalized)
    assert payload["projects"][0]["description"] == "Scope Implementation Outcome"
    assert payload["certifications"] == [
        {"title": "Siemens — SIMATIC S7 Programming, 2022"}
    ]
