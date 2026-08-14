import json

import pytest

from ljpa_reworked.services.harness.protocol import parse_terminal_result


def test_parse_terminal_result_success():
    line = json.dumps({"event": "result", "result": {"status": "SUCCESS", "details": "done"}})
    is_terminal, is_success = parse_terminal_result(line)
    assert is_terminal is True
    assert is_success is True


def test_parse_terminal_result_error():
    line = json.dumps({"event": "result", "result": {"status": "ERROR", "message": "failed"}})
    is_terminal, is_success = parse_terminal_result(line)
    assert is_terminal is True
    assert is_success is False


def test_parse_terminal_result_non_terminal_events():
    line = json.dumps({"event": "message", "content": "status: SUCCESS"})
    is_terminal, is_success = parse_terminal_result(line)
    assert is_terminal is False
    assert is_success is False


def test_parse_terminal_result_malformed_json_and_prose():
    assert parse_terminal_result("not json SUCCESS") == (False, False)
    assert parse_terminal_result("  ") == (False, False)
    assert parse_terminal_result("123") == (False, False)
    assert parse_terminal_result("null") == (False, False)


def test_parse_terminal_result_missing_keys():
    assert parse_terminal_result(json.dumps({"event": "result"})) == (True, False)
    assert parse_terminal_result(json.dumps({"other": "value"})) == (False, False)


@pytest.mark.asyncio
async def test_server_stops_agy_process_group_after_terminal_event():
    import signal
    from unittest.mock import MagicMock, patch

    from ljpa_reworked.services.harness.harness_server import agy_stream_generator

    mock_process = MagicMock()
    mock_process.pid = 9999
    mock_process.stdout = [
        '{"event": "message", "content": "working"}\n',
        '{"event": "result", "result": {"status": "SUCCESS"}}\n',
        '{"event": "message", "content": "orphaned after result"}\n',
    ]
    mock_process.poll.return_value = None

    with patch("subprocess.Popen", return_value=mock_process) as mock_popen, \
         patch("os.getpgid", return_value=9999) as mock_getpgid, \
         patch("os.killpg") as mock_killpg:

        lines = []
        async for line in agy_stream_generator(["agy", "run"]):
            lines.append(line)

        assert mock_popen.call_args.kwargs.get("start_new_session") is True
        assert len(lines) == 2
        assert '{"event": "result"' in lines[1]
        mock_getpgid.assert_called_with(9999)
        mock_killpg.assert_any_call(9999, signal.SIGTERM)


def test_harness_scraper_prompt_contract():
    from pathlib import Path

    prompt_path = Path("prompts/harness_scraper.md")
    assert prompt_path.exists()
    content = prompt_path.read_text(encoding="utf-8")

    assert "Do not use background execution" in content
    assert "Stay in the foreground" in content
    assert "/workspace/scraper-result.json" not in content
