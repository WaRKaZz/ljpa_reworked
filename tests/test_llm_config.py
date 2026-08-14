from unittest.mock import MagicMock, patch

import pytest
from crewai import LLM


def test_create_llm_uses_openai_provider_for_configured_gateway(monkeypatch):
    import ljpa_reworked.config as config

    monkeypatch.setattr(config, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(config, "LLM_MODEL", "ag/gemini-3.6-flash-high")
    monkeypatch.setattr(config, "LLM_BASE_URL", "http://id-vps:20128/v1")
    llm = MagicMock()
    with patch("crewai.LLM", return_value=llm) as llm_class:
        assert config.create_llm() is llm
    llm_class.assert_called_once_with(
        model="openai/ag/gemini-3.6-flash-high",
        api_key="test-key",
        base_url="http://id-vps:20128/v1",
    )


def test_create_llm_does_not_duplicate_openai_prefix(monkeypatch):
    import ljpa_reworked.config as config

    monkeypatch.setattr(config, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(config, "LLM_MODEL", "openai/ag/gemini-3.6-flash-high")
    llm = MagicMock()
    with patch("crewai.LLM", return_value=llm) as llm_class:
        config.create_llm()
    assert llm_class.call_args.kwargs["model"] == "openai/ag/gemini-3.6-flash-high"


@pytest.mark.parametrize(
    ("module_name", "class_name"),
    [
        (
            "ljpa_reworked.crews.resume_generation_crew.resume_generation_crew",
            "ResumeGenerationCrew",
        ),
        (
            "ljpa_reworked.crews.resume_evaluation_crew.resume_evaluation_crew",
            "ResumeEvaluationCrew",
        ),
        (
            "ljpa_reworked.crews.email_generation_crew.email_generation_crew",
            "EmailGenerationCrew",
        ),
    ],
)
def test_resume_related_crews_use_shared_llm_factory(
    monkeypatch, module_name, class_name
):
    import importlib

    module = importlib.import_module(module_name)
    shared_llm = LLM(
        model="openai/gpt-4o-mini", api_key="test-key", base_url="http://gateway/v1"
    )
    factory = MagicMock(return_value=shared_llm)
    monkeypatch.setattr(module, "create_llm", factory)

    crew = getattr(module, class_name)()

    assert crew.llm is shared_llm
    factory.assert_called_once()


def test_config_imports_without_cv_file_name(monkeypatch):
    import importlib

    import dotenv

    import ljpa_reworked.config as config

    monkeypatch.delenv("CV_FILE_NAME", raising=False)
    monkeypatch.setattr(dotenv, "load_dotenv", lambda: False)
    importlib.reload(config)
    assert config.CV_FILE_PATH is None
