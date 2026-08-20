import json
import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from ljpa_reworked.services.harness_runner import (
    HarnessScraperResult,
    harness_save_scraper_skill,
    harness_save_site_skill,
    harness_submit,
    run_linkedin_harness,
)


def test_run_linkedin_harness_sends_http_request(tmp_path):
    canonical = tmp_path / "app.db"
    scraper = tmp_path / "harness-scraper" / "app.db"
    with sqlite3.connect(canonical) as connection:
        connection.execute("CREATE TABLE marker (value TEXT)")

    mock_response = MagicMock()
    mock_response.__enter__.return_value = [
        b'{"event":"result","result":{"status":"SUCCESS"}}\n'
    ]

    def side_effect_urlopen(*args, **kwargs):
        artifact = scraper.with_name("scraper-result.json")
        artifact.write_text(
            json.dumps(
                {
                    "status": "completed",
                    "workspace_db": "/app/data/app.db",
                    "integrity_check": "ok",
                    "foreign_key_check": "ok",
                    "final_valid_vacancy_count": 1,
                }
            )
        )
        return mock_response

    with patch(
        "urllib.request.urlopen", side_effect=side_effect_urlopen
    ) as mock_urlopen:
        assert (
            run_linkedin_harness(
                api_url="http://localhost:8080/run-harness",
                canonical_db_path=canonical,
                scraper_db_path=scraper,
            )
            == 0
        )
    assert not scraper.exists()

    assert mock_urlopen.called
    req = mock_urlopen.call_args.args[0]
    assert req.full_url == "http://localhost:8080/run-harness"
    assert req.get_method() == "POST"


def test_scraper_runner_returns_at_terminal_agy_success(tmp_path):
    canonical = tmp_path / "app.db"
    scraper = tmp_path / "harness-scraper" / "app.db"
    with sqlite3.connect(canonical) as connection:
        connection.execute("CREATE TABLE marker (value TEXT)")

    consumed = []

    def response_lines():
        consumed.append("line1")
        yield b'{"event":"message","content":"working"}\n'
        consumed.append("line2")
        yield b'{"event":"result","result":{"status":"SUCCESS"}}\n'
        consumed.append("line3")
        yield b'{"event":"message","content":"should not be read"}\n'

    mock_response = MagicMock()
    mock_response.__enter__.return_value = response_lines()

    with patch("urllib.request.urlopen", return_value=mock_response):
        run_linkedin_harness(
            api_url="http://localhost:8080/run-harness",
            canonical_db_path=canonical,
            scraper_db_path=scraper,
        )

    assert consumed == ["line1", "line2"]


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
            timeout="1h",
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
    assert payload["timeout"] == "1h"


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
            from ljpa_reworked.services.harness_runner import main as cli_main

            with pytest.raises(SystemExit) as exit_info:
                cli_main()

    assert exit_info.value.code == 0
    mock_submit.assert_called_once_with(
        vacancy_url="https://example.com/job/123",
        resume_path="/app/resources/resumes/test.pdf",
        prompt_file="/app/prompts/harness_submit.md",
        timeout="1h",
        api_url="http://localhost:8080/run-harness",
    )


def test_harness_submit_extracts_conversation_id_and_retains_80_line_tail():
    lines = [
        f'{{"event":"step","index":{i},"conversation_id":"conv-abc-123"}}\n'.encode()
        for i in range(100)
    ]
    lines.append(b'{"status":"success","message":"finished"}\n')

    mock_response = MagicMock()
    mock_response.__enter__.return_value = lines

    with patch("urllib.request.urlopen", return_value=mock_response):
        result = harness_submit(
            vacancy_url="https://example.com/apply",
            resume_path="/app/resources/resumes/resume_1.pdf",
            api_url="http://localhost:8080/run-harness",
        )

    assert hasattr(result, "conversation_id")
    assert result.conversation_id == "conv-abc-123"
    assert hasattr(result, "tail_lines")
    assert len(result.tail_lines) == 80
    assert result.completed is True
    assert result == 0
    assert '"index":99' in result.tail_lines[-2]


def test_harness_submit_extracts_first_conversation_id_and_does_not_overwrite():
    lines = [
        b'{"event":"step","conversation_id":"first-cid-123"}\n',
        b'{"event":"step","conversation_id":"second-cid-456"}\n',
        b'{"event":"result","result":{"status":"SUCCESS","conversation_id":"third-cid-789"}}\n',
    ]
    mock_response = MagicMock()
    mock_response.__enter__.return_value = lines

    with patch("urllib.request.urlopen", return_value=mock_response):
        result = harness_submit(
            vacancy_url="https://example.com/apply",
            resume_path="/app/resources/resumes/resume_1.pdf",
            api_url="http://localhost:8080/run-harness",
        )

    assert result.conversation_id == "first-cid-123"


def test_harness_save_site_skill_uses_finite_http_timeout():
    mock_response = MagicMock()
    mock_response.__enter__.return_value = [
        b'{"event":"result","result":{"status":"SUCCESS"}}\n'
    ]

    with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
        res = harness_save_site_skill(
            conversation_id="conv-cid-99",
            timeout="15m",
            api_url="http://localhost:8080/run-harness",
        )
        assert res == 0

    assert mock_urlopen.called
    kwargs = mock_urlopen.call_args.kwargs
    assert "timeout" in kwargs
    assert isinstance(kwargs["timeout"], (int, float))
    assert kwargs["timeout"] > 0


def test_harness_save_site_skill_succeeds_when_skill_file_activity_present():
    mock_response = MagicMock()
    mock_response.__enter__.return_value = [
        b'{"event":"step_update","step_update":{"tool_name":"replace_file_content","tool_info":{"parameters":{"TargetFile":"/runtime/workspace/README.md"}}}}\n',
        b'{"event":"result","result":{"status":"ERROR","error":"timeout waiting for response"}}\n',
    ]

    with patch("urllib.request.urlopen", return_value=mock_response):
        res = harness_save_site_skill(
            conversation_id="conv-cid-99",
            timeout="15m",
            api_url="http://localhost:8080/run-harness",
        )
        assert res == 0


def test_harness_save_site_skill_fails_when_no_success_or_activity():
    mock_response = MagicMock()
    mock_response.__enter__.return_value = [
        b'{"event":"result","result":{"status":"ERROR","error":"timeout waiting for response"}}\n'
    ]

    with patch("urllib.request.urlopen", return_value=mock_response):
        with pytest.raises(
            RuntimeError, match="Skill-save harness process did not report success"
        ):
            harness_save_site_skill(
                conversation_id="conv-cid-99",
                timeout="15m",
                api_url="http://localhost:8080/run-harness",
            )


def test_harness_scraper_result_equality_and_int_conversion():
    res_success = HarnessScraperResult(
        completed=True, conversation_id="conv-1", tail_lines=["line1"]
    )
    res_success_dup = HarnessScraperResult(
        completed=True, conversation_id="conv-1", tail_lines=["line1"]
    )
    res_fail = HarnessScraperResult(
        completed=False, conversation_id="conv-2", tail_lines=[]
    )

    assert res_success == 0
    assert res_success != 1
    assert int(res_success) == 0
    assert res_fail == 1
    assert res_fail != 0
    assert int(res_fail) == 1
    assert res_success == res_success_dup
    assert res_success != res_fail
    assert res_success != "unrelated"


def test_run_linkedin_harness_returns_scraper_result_with_conversation_id(tmp_path):
    canonical = tmp_path / "app.db"
    scraper = tmp_path / "harness-scraper" / "app.db"
    with sqlite3.connect(canonical) as connection:
        connection.execute("CREATE TABLE marker (value TEXT)")

    lines = [
        f'{{"event":"step","index":{i},"conversation_id":"conv-scraper-777"}}\n'.encode()
        for i in range(100)
    ]
    lines.append(b'{"event":"result","result":{"status":"SUCCESS"}}\n')

    mock_response = MagicMock()
    mock_response.__enter__.return_value = lines

    with patch("urllib.request.urlopen", return_value=mock_response):
        result = run_linkedin_harness(
            api_url="http://localhost:8080/run-harness",
            canonical_db_path=canonical,
            scraper_db_path=scraper,
        )

    assert isinstance(result, HarnessScraperResult)
    assert result.completed is True
    assert result.conversation_id == "conv-scraper-777"
    assert len(result.tail_lines) == 80
    assert result == 0
    assert int(result) == 0
    assert not scraper.exists()


def test_run_linkedin_harness_returns_failed_scraper_result_on_error(tmp_path):
    canonical = tmp_path / "app.db"
    scraper = tmp_path / "harness-scraper" / "app.db"
    with sqlite3.connect(canonical) as connection:
        connection.execute("CREATE TABLE marker (value TEXT)")

    lines = [
        b'{"event":"step","conversation_id":"conv-scraper-err"}\n',
        b'{"event":"result","result":{"status":"ERROR","error":"crashed"}}\n',
    ]

    mock_response = MagicMock()
    mock_response.__enter__.return_value = lines

    with patch("urllib.request.urlopen", return_value=mock_response):
        result = run_linkedin_harness(
            api_url="http://localhost:8080/run-harness",
            canonical_db_path=canonical,
            scraper_db_path=scraper,
        )

    assert isinstance(result, HarnessScraperResult)
    assert result.completed is False
    assert result.conversation_id == "conv-scraper-err"
    assert len(result.tail_lines) == 2
    assert result == 1
    assert not scraper.exists()


def test_harness_save_scraper_skill_uses_finite_http_timeout():
    mock_response = MagicMock()
    mock_response.__enter__.return_value = [
        b'{"event":"result","result":{"status":"SUCCESS"}}\n'
    ]

    with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
        res = harness_save_scraper_skill(
            conversation_id="conv-scraper-777",
            timeout="15m",
            api_url="http://localhost:8080/run-harness",
        )
        assert res == 0

    assert mock_urlopen.called
    req = mock_urlopen.call_args.args[0]
    assert req.full_url == "http://localhost:8080/run-harness"
    assert req.get_method() == "POST"
    payload = json.loads(req.data.decode("utf-8"))
    assert payload["conversation_id"] == "conv-scraper-777"
    assert payload["prompt_file"] == "/app/prompts/harness_save_scraper_skill.md"
    assert payload["timeout"] == "15m"

    kwargs = mock_urlopen.call_args.kwargs
    assert "timeout" in kwargs
    assert isinstance(kwargs["timeout"], (int, float))
    assert kwargs["timeout"] > 0


def test_harness_save_scraper_skill_succeeds_when_skill_file_activity_present():
    mock_response = MagicMock()
    mock_response.__enter__.return_value = [
        b'{"event":"step_update","step_update":{"tool_name":"replace_file_content","tool_info":{"parameters":{"TargetFile":"/runtime/workspace/linkedin_posts_scraper/SKILL.md"}}}}\n',
        b'{"event":"result","result":{"status":"ERROR","error":"timeout waiting for response"}}\n',
    ]

    with patch("urllib.request.urlopen", return_value=mock_response):
        res = harness_save_scraper_skill(
            conversation_id="conv-scraper-777",
            timeout="15m",
            api_url="http://localhost:8080/run-harness",
        )
        assert res == 0


def test_harness_save_scraper_skill_fails_when_no_success_or_activity():
    mock_response = MagicMock()
    mock_response.__enter__.return_value = [
        b'{"event":"result","result":{"status":"ERROR","error":"timeout waiting for response"}}\n'
    ]

    with patch("urllib.request.urlopen", return_value=mock_response):
        with pytest.raises(
            RuntimeError,
            match="Scraper skill-save harness process did not report success",
        ):
            harness_save_scraper_skill(
                conversation_id="conv-scraper-777",
                timeout="15m",
                api_url="http://localhost:8080/run-harness",
            )


def test_harness_save_scraper_skill_requires_conversation_id():
    with pytest.raises(ValueError, match="conversation_id is required"):
        harness_save_scraper_skill(conversation_id="")

    with pytest.raises(ValueError, match="conversation_id is required"):
        harness_save_scraper_skill(conversation_id=None)
