from unittest.mock import MagicMock, patch


def test_resume_task_uses_agent_timeout_not_unsupported_task_timeout():
    from ljpa_reworked.crews.resume_generation_crew.resume_generation_crew import (
        ResumeGenerationCrew,
    )

    task = ResumeGenerationCrew().resume_generation_task()
    assert "max_execution_time" not in task.model_fields_set


def test_create_llm_uses_current_custom_openai_endpoint_parameters(monkeypatch):
    import ljpa_reworked.config as config

    monkeypatch.setattr(config, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(config, "LLM_MODEL", "gateway/model")
    monkeypatch.setattr(config, "LLM_BASE_URL", "http://gateway/v1")
    with patch("crewai.LLM", return_value=MagicMock()) as llm_class:
        config.create_llm()

    assert llm_class.call_args.kwargs == {
        "model": "openai/gateway/model",
        "api_key": "test-key",
        "base_url": "http://gateway/v1",
    }


def test_create_llm_requires_a_configured_model(monkeypatch):
    import ljpa_reworked.config as config

    monkeypatch.setattr(config, "LLM_MODEL", None)
    try:
        config.create_llm()
    except ValueError as error:
        assert "LLM_MODEL" in str(error)
    else:
        raise AssertionError("missing LLM_MODEL must fail clearly")
