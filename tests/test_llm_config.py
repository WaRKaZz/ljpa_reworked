from unittest.mock import MagicMock, patch


def test_create_llm_uses_configured_openai_compatible_gateway(monkeypatch):
    import ljpa_reworked.config as config

    monkeypatch.setattr(config, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(config, "LLM_MODEL", "openai/test-model")
    monkeypatch.setattr(config, "LLM_BASE_URL", "http://id-vps:20128/v1")
    llm = MagicMock()
    with patch("crewai.LLM", return_value=llm) as llm_class:
        assert config.create_llm() is llm
    llm_class.assert_called_once_with(
        model="openai/test-model", api_key="test-key",
        base_url="http://id-vps:20128/v1", custom_openai=True,
    )


def test_config_imports_without_cv_file_name(monkeypatch):
    import importlib

    import dotenv

    import ljpa_reworked.config as config

    monkeypatch.delenv("CV_FILE_NAME", raising=False)
    monkeypatch.setattr(dotenv, "load_dotenv", lambda: False)
    importlib.reload(config)
    assert config.CV_FILE_PATH is None
