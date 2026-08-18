import sys
from unittest.mock import MagicMock

# Ensure mock modules exist for host testing when optional container dependencies aren't installed locally
mock_langchain_openai = MagicMock()
mock_browser_use = MagicMock()

sys.modules.setdefault("langchain_openai", mock_langchain_openai)
sys.modules.setdefault("browser_use", mock_browser_use)

from ljpa_reworked.services.docker.browser_use_mcp import (  # noqa: E402
    get_browser,
    get_llm,
)


def test_browser_use_mcp_env_isolation(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://custom-endpoint:20128/v1")
    monkeypatch.setenv("LLM_API_KEY", "test_key_abc123")
    monkeypatch.setenv("BROWSER_USE_MODEL", "free-tier")
    monkeypatch.setenv("LLM_MODEL", "gemini/gemini-3.5-flash-lite")

    mock_chat_openai = MagicMock()
    mock_langchain_openai.ChatOpenAI = mock_chat_openai

    llm = get_llm()
    mock_chat_openai.assert_called_once_with(
        model="free-tier",
        openai_api_base="http://custom-endpoint:20128/v1",
        openai_api_key="test_key_abc123",
        temperature=0.0,
    )
    assert llm == mock_chat_openai.return_value


def test_browser_use_mcp_cdp_connection(monkeypatch):
    monkeypatch.setenv("CDP_URL", "http://cloak-browser:9222")

    mock_browser_cls = MagicMock()
    mock_browser_use.Browser = mock_browser_cls

    b = get_browser()
    mock_browser_cls.assert_called_once_with(cdp_url="http://cloak-browser:9222")
    assert b == mock_browser_cls.return_value
