import json
from unittest.mock import MagicMock, patch

from ljpa_reworked.services.harness_runner import harness_submit, run_linkedin_harness


def test_run_linkedin_harness_sends_http_request():
    mock_response = MagicMock()
    mock_response.__enter__.return_value = [b'{"event":"init"}\n']

    with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
        assert run_linkedin_harness(api_url="http://localhost:8080/run-harness") == 0

    assert mock_urlopen.called
    req = mock_urlopen.call_args.args[0]
    assert req.full_url == "http://localhost:8080/run-harness"
    assert req.get_method() == "POST"


def test_harness_submit_sends_payload_and_returns_0_on_confirmed_status():
    mock_response = MagicMock()
    mock_response.__enter__.return_value = [
        b'{"status": "confirmed_submitted", "vacancy_url": "https://example.com/apply"}\n',
        b'{"status": "success", "message": "agy process finished successfully"}\n',
    ]

    with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
        result = harness_submit(
            vacancy_url="https://example.com/apply",
            resume_path="/app/resources/resumes/resume_1.pdf",
            prompt_file="/app/prompts/harness_submit.md",
            timeout="8h",
            api_url="http://localhost:8080/run-harness",
        )
        assert result == 0

    req = mock_urlopen.call_args.args[0]
    assert req.full_url == "http://localhost:8080/run-harness"
    assert req.get_method() == "POST"
    payload = json.loads(req.data.decode("utf-8"))
    assert payload["vacancy_url"] == "https://example.com/apply"
    assert payload["resume_path"] == "/app/resources/resumes/resume_1.pdf"
    assert payload["prompt_file"] == "/app/prompts/harness_submit.md"
    assert payload["timeout"] == "8h"


def test_harness_submit_returns_nonzero_on_failure_or_missing_confirmation():
    mock_response = MagicMock()
    mock_response.__enter__.return_value = [
        b'{"status": "error", "message": "harness completed without confirmed submission"}\n'
    ]

    with patch("urllib.request.urlopen", return_value=mock_response):
        result = harness_submit(
            vacancy_url="https://example.com/apply",
            resume_path="/app/resources/resumes/resume_1.pdf",
            api_url="http://localhost:8080/run-harness",
        )
        assert result == 1


def test_harness_runner_cli_manual_one_vacancy_path():
    test_args = [
        "harness_runner",
        "--url",
        "https://example.com/job/123",
        "--pdf-path",
        "/app/resources/resumes/test.pdf",
        "--api-url",
        "http://localhost:8080/run-harness",
    ]
    with patch("sys.argv", test_args):
        with patch(
            "ljpa_reworked.services.harness_runner.harness_submit", return_value=0
        ) as mock_submit:
            with patch("sys.exit") as mock_exit:
                from ljpa_reworked.services.harness_runner import main as cli_main

                cli_main()
                mock_submit.assert_called_once_with(
                    vacancy_url="https://example.com/job/123",
                    resume_path="/app/resources/resumes/test.pdf",
                    prompt_file="/app/prompts/harness_submit.md",
                    timeout="8h",
                    api_url="http://localhost:8080/run-harness",
                )
                mock_exit.assert_called_once_with(0)
