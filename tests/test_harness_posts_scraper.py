from unittest.mock import MagicMock, patch

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
