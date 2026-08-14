from crewai.tasks.task_output import TaskOutput


def test_guardrail_feedback_includes_required_replacement_json_shape():
    from ljpa_reworked.crews.resume_generation_crew.resume_generation_crew import (
        resume_output_guardrail,
    )

    allowed, feedback = resume_output_guardrail(
        TaskOutput(
            description="resume",
            raw='''{"projects":[{"title":"FGP","highlights":["One factual result"]}]}''',
            agent="resume_agent",
        )
    )

    assert not allowed
    assert '"highlights": ["fact 1", "fact 2", "fact 3"]' in feedback
    assert "previous output had 1" in feedback
    assert "Return only the complete JSON object" in feedback
