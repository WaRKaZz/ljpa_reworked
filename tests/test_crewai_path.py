from unittest.mock import MagicMock, patch

from ljpa_reworked.models.crewai_pydantic_models import BasicEvaluationCrewAI


def test_resume_generation_uses_crewai_task_so_guardrail_can_retry(tmp_path):
    from ljpa_reworked.crew_workflow import crewai_generate_resume

    profile = tmp_path / "profile.md"
    profile.write_text(
        "## General Information\n- **Name:** A\n- **Target Title:** Controls Engineer\n- **Location:** A\n## Job Search Preferences\n- **Email:** a@example.com\n- **Phone:** 1\n## Summary\nSummary\n## Experience\n### Co — Engineer\n**Dates:** 2014 – Now\n**Location:** A\n- Source fact.\n## Education\n### U\n**Degree:** BSc\n**Dates:** 2010 – 2014\n## Skills\nSkills\n",
        encoding="utf-8",
    )
    vacancy = MagicMock(title="Controls Engineer", text="PLC role")
    evaluation = BasicEvaluationCrewAI(summary="fit", rating=80)
    output = MagicMock()
    output.raw = """{
        "personal_info":{"name":"A","email":"a@example.com","phone":"1","address":"A","location":"A"},
        "summary":"Automation engineer",
        "education":[{"course":"BSc","institution":"U","location":"A","start_date":"2010","end_date":"2014"}],
        "experience":[{"title":"Engineer","company":"Co","location":"A","start_date":"2014","end_date":"Now","description":["One","Two","Three"]}],
        "skills":[{"title":"PLC","elements":["TIA"]}],
        "projects":[]
    }"""

    with (
        patch("ljpa_reworked.crew_workflow.PROFILE_FILE_PATH", str(profile)),
        patch("ljpa_reworked.crew_workflow.ResumeGenerationCrew") as crew_class,
    ):
        crew = crew_class.return_value.crew.return_value
        crew.kickoff.return_value = output
        output.token_usage.successful_requests = 1
        result = crewai_generate_resume(vacancy, evaluation)

    assert result.personal_info.name == "A"
    crew_class.return_value.crew.return_value.kickoff.assert_called_once()
    inputs = crew_class.return_value.crew.return_value.kickoff.call_args.kwargs[
        "inputs"
    ]
    assert inputs["title"] == "Controls Engineer"
    assert inputs["rating"] == 80
    assert inputs["missing_mandatory_facts"] == []
