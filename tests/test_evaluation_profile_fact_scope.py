from unittest.mock import MagicMock, patch

from ljpa_reworked.models.crewai_pydantic_models import BasicEvaluationCrewAI


def test_evaluation_does_not_treat_vacancy_requirements_as_missing_profile_facts(
    tmp_path,
):
    from ljpa_reworked.crew_workflow import crewai_evaluate_vacancy

    profile = tmp_path / "profile.md"
    profile.write_text(
        """## General Information
- **Name:** A
- **Target Title:** Controls Engineer
- **Location:** A
## Job Search Preferences
- **Email:** a@example.com
- **Phone:** 1
## Summary
Summary
## Experience
### Co — Engineer
**Dates:** 2014 – Now
**Location:** A
- Source fact.
## Education
### U
**Degree:** MSc Automation
**Dates:** 2010 – 2014
## Skills
PLC
""",
        encoding="utf-8",
    )
    vacancy = MagicMock(
        title="Data Center Engineer", text="Requires data center experience"
    )
    output = MagicMock()
    output.tasks_output = [
        MagicMock(
            pydantic=BasicEvaluationCrewAI(
                summary="Candidate lacks direct data center experience.",
                rating=65,
                missing_mandatory_facts=["Direct data center engineering experience."],
            )
        )
    ]
    output.token_usage.successful_requests = 1

    with (
        patch("ljpa_reworked.crew_workflow.PROFILE_FILE_PATH", str(profile)),
        patch("ljpa_reworked.crew_workflow.ResumeEvaluationCrew") as crew_class,
    ):
        crew_class.return_value.crew.return_value.kickoff.return_value = output
        result = crewai_evaluate_vacancy(vacancy)

    assert result.missing_mandatory_facts == []
