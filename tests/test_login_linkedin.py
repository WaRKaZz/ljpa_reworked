from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ljpa_reworked.services.auth.login_linkedin import (
    DEFAULT_SAVE_PATH,
    check_login_success,
    clean_env_val,
    fill_login_form,
    get_cdp_endpoint,
)


def test_clean_env_val():
    assert clean_env_val('"email@mail.com"') == "email@mail.com"
    assert clean_env_val("'password123'") == "password123"
    assert clean_env_val("plain") == "plain"
    assert clean_env_val(None) == ""


def test_get_cdp_endpoint():
    with patch.dict("os.environ", {"CDP_URL": "http://localhost:9222"}):
        assert "fingerprint=linkedin_seed" in get_cdp_endpoint()
    with patch.dict("os.environ", {}, clear=True):
        assert "http://localhost:9222" in get_cdp_endpoint()


@pytest.mark.asyncio
async def test_fill_login_form():
    mock_page = MagicMock()
    mock_user_locator = MagicMock()
    mock_user_locator.count = AsyncMock(return_value=1)
    mock_user_locator.first.fill = AsyncMock()

    mock_pass_locator = MagicMock()
    mock_pass_locator.first.fill = AsyncMock()

    mock_btn_locator = MagicMock()
    mock_btn_locator.count = AsyncMock(return_value=1)
    mock_btn_locator.first.click = AsyncMock()

    def locator_side_effect(selector):
        if "email" in selector or "username" in selector:
            return mock_user_locator
        if "password" in selector:
            return mock_pass_locator
        return mock_btn_locator

    mock_page.locator.side_effect = locator_side_effect

    res = await fill_login_form(mock_page, "user@mail.com", "secret")
    assert res is True
    mock_user_locator.first.fill.assert_called_once_with("user@mail.com")
    mock_pass_locator.first.fill.assert_called_once_with("secret")
    mock_btn_locator.first.click.assert_called_once()


@pytest.mark.asyncio
async def test_check_login_success_detected(tmp_path):
    mock_page = MagicMock()
    mock_page.url = "https://www.linkedin.com/feed/"
    mock_locator = MagicMock()
    mock_locator.count = AsyncMock(return_value=1)
    mock_page.locator.return_value = mock_locator

    mock_context = MagicMock()
    mock_context.storage_state = AsyncMock()
    state_file = tmp_path / "resources" / "state.json"

    result = await check_login_success(
        mock_page, mock_context, state_path=state_file, poll_interval=0.01, timeout=1.0
    )
    assert result is True
    mock_context.storage_state.assert_called_once_with(path=str(state_file))


def test_default_save_path_is_under_data():
    assert DEFAULT_SAVE_PATH.as_posix() == "data/state.json"


@pytest.mark.asyncio
async def test_login_linkedin_main_success(tmp_path):
    from ljpa_reworked.services.auth.login_linkedin import main as login_main

    mock_browser = AsyncMock()
    mock_context = MagicMock()
    mock_page = MagicMock()
    mock_page.url = "https://www.linkedin.com/feed/"

    mock_browser.contexts = [mock_context]
    mock_context.pages = [mock_page]
    mock_context.storage_state = AsyncMock()

    mock_locator = MagicMock()
    mock_locator.count = AsyncMock(return_value=1)
    mock_page.locator.return_value = mock_locator

    mock_p = MagicMock()
    mock_p.chromium.connect_over_cdp = AsyncMock(return_value=mock_browser)

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_p)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "ljpa_reworked.services.auth.login_linkedin.async_playwright",
            return_value=mock_cm,
        ),
        patch.dict(
            "os.environ",
            {"LINKEDIN_EMAIL": "test@example.com", "LINKEDIN_PASSWORD": "pass"},
        ),
    ):
        res = await login_main(state_path=tmp_path / "state.json")
        assert res is True
        mock_browser.close.assert_called_once()
