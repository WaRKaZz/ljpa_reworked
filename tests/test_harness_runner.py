from unittest.mock import MagicMock, patch

from ljpa_reworked.services.harness_runner import run_linkedin_harness


def test_run_linkedin_harness_sends_http_request():
    mock_response = MagicMock()
    mock_response.__enter__.return_value = [b'{"event":"init"}\n']

    with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
        assert run_linkedin_harness(api_url="http://localhost:8080/run-harness") == 0

    assert mock_urlopen.called
    req = mock_urlopen.call_args.args[0]
    assert req.full_url == "http://localhost:8080/run-harness"
    assert req.get_method() == "POST"
