import asyncio
import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

# Import the module to test
import ljpa_reworked.auth.login_harness as lh

@pytest.mark.asyncio
async def test_check_login_success_detects_login(tmp_path):
    """Test that check_login_success detects login and saves state."""
    # Mock page and context
    page = AsyncMock()
    context = AsyncMock()
    
    # Configure the locator to return count > 0 (meaning successful login)
    locator = AsyncMock()
    locator.count.return_value = 1
    page.locator.return_value = locator

    # Change working directory to tmp_path so 'auth' dir is created there
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        # Run the check function
        result = await lh.check_login_success(page, context)
        
        # Assertions
        assert result is True
        page.locator.assert_called_once_with(".global-nav__me")
        context.storage_state.assert_called_once_with(path="auth/state.json")
        assert os.path.exists("auth")
    finally:
        os.chdir(original_cwd)

@pytest.mark.asyncio
async def test_check_login_success_waits(tmp_path):
    """Test that it waits and retries if login not detected immediately."""
    page = AsyncMock()
    context = AsyncMock()
    
    # Configure the locator to return 0 on first call, then 1 on second
    locator_0 = AsyncMock()
    locator_0.count.return_value = 0
    
    locator_1 = AsyncMock()
    locator_1.count.return_value = 1
    
    page.locator.side_effect = [locator_0, locator_1]

    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    
    try:
        # Use patch to speed up sleep
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            result = await lh.check_login_success(page, context)
            
            assert result is True
            assert page.locator.call_count == 2
            mock_sleep.assert_called_once_with(5)
            context.storage_state.assert_called_once_with(path="auth/state.json")
    finally:
        os.chdir(original_cwd)
