import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path
from ljpa_reworked.auth.login_linkedin import check_login_success, get_cdp_endpoint

def test_get_cdp_endpoint():
    with patch.dict("os.environ", {"CDP_URL": "http://cloak-browser:9222"}):
        assert get_cdp_endpoint() == "http://cloak-browser:9222"
    with patch.dict("os.environ", {}, clear=True):
        assert get_cdp_endpoint() == "http://localhost:9222"
    with patch.dict("os.environ", {"CDP_URL": "cloak-browser:9222"}):
        assert get_cdp_endpoint() == "http://cloak-browser:9222"

@pytest.mark.asyncio
async def test_check_login_success_detected(tmp_path):
    mock_page = MagicMock()
    mock_locator = MagicMock()
    mock_locator.count = AsyncMock(return_value=1)
    mock_page.locator.return_value = mock_locator

    mock_context = MagicMock()
    mock_context.storage_state = AsyncMock()
    state_file = tmp_path / "state.json"

    result = await check_login_success(mock_page, mock_context, state_path=state_file, poll_interval=0.01, timeout=1.0)
    assert result is True
    mock_context.storage_state.assert_called_once_with(path=str(state_file))

@pytest.mark.asyncio
async def test_check_login_success_timeout(tmp_path):
    mock_page = MagicMock()
    mock_locator = MagicMock()
    mock_locator.count = AsyncMock(return_value=0)
    mock_page.locator.return_value = mock_locator

    mock_context = MagicMock()
    mock_context.storage_state = AsyncMock()
    state_file = tmp_path / "state.json"

    result = await check_login_success(mock_page, mock_context, state_path=state_file, poll_interval=0.01, timeout=0.05)
    assert result is False
    mock_context.storage_state.assert_not_called()
