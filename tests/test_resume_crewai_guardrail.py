from crewai.tasks.task_output import TaskOutput


def test_resume_generation_task_retries_project_with_fewer_than_three_highlights():
    from ljpa_reworked.crews.resume_generation_crew.resume_generation_crew import (
        resume_output_guardrail,
    )

    allowed, feedback = resume_output_guardrail(
        TaskOutput(
            description="resume",
            raw="""{"projects":[{"title":"Flow Monitoring System Telemetry Deployment","highlights":["Only one"]}]}""",
            agent="resume_agent",
        )
    )

    assert not allowed
    assert "Flow Monitoring System Telemetry Deployment" in feedback
    assert "exactly three or four distinct JSON strings" in feedback


def test_resume_generation_task_has_crewai_guardrail():
    from ljpa_reworked.crews.resume_generation_crew.resume_generation_crew import (
        ResumeGenerationCrew,
    )

    assert ResumeGenerationCrew().resume_generation_task().guardrail is not None


def test_resume_generation_task_uses_eight_guardrail_retries():
    from ljpa_reworked.crews.resume_generation_crew.resume_generation_crew import (
        ResumeGenerationCrew,
    )

    assert ResumeGenerationCrew().resume_generation_task().guardrail_max_retries == 8
