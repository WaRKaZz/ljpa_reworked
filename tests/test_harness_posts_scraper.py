from unittest.mock import MagicMock, patch, AsyncMock

from ljpa_reworked.config import AGY_BIN_PATH
from ljpa_reworked.services.harness_posts_scraper import run_agy_harness_1


def test_run_agy_harness_1_executes_local_cmd():
    mock_res = MagicMock()
    mock_res.stdout = "AGY Agent completed successfully."

    with patch("subprocess.run", return_value=mock_res) as mock_run:
        res = run_agy_harness_1()

        mock_run.assert_called_once()
        cmd_args = mock_run.call_args[0][0]
        assert cmd_args[0] == AGY_BIN_PATH
        assert cmd_args[1] == "--print"
        assert res == "AGY Agent completed successfully."

import pytest
from ljpa_reworked.services.harness.posts_scraper import run_linkedin_posts_agent, run_agy_harness_sdk

def test_run_linkedin_posts_agent_delegates_to_container():
    mock_res = MagicMock()
    mock_res.stdout = "OK\n"
    with patch("subprocess.run", return_value=mock_res) as mock_run:
        res = run_linkedin_posts_agent(verbose=False)
        assert res == "OK"
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "podman"
        assert cmd[1] == "exec"
        assert cmd[3] == "antigravity-cli-dev"
        assert cmd[4] == "python"
        assert cmd[5] == "/app/linkedin_posts_agent.py"

def test_run_agy_harness_sdk_executes_podman_exec():
    mock_res = MagicMock()
    mock_res.stdout = "SDK output\n"
    
    with patch("subprocess.run", return_value=mock_res) as mock_run:
        res = run_agy_harness_sdk("Test prompt", verbose=False)

        mock_run.assert_called_once()
        cmd_args = mock_run.call_args[0][0]
        assert cmd_args[0] == "podman"
        assert cmd_args[1] == "exec"
        assert cmd_args[3] == "antigravity-cli-dev"
        assert cmd_args[4] == "python"
        assert cmd_args[5] == "/app/linkedin_posts_agent.py"
        
        assert mock_run.call_args[1]["input"] == "Test prompt"
        assert res == "SDK output"

