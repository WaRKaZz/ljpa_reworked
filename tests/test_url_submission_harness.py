from unittest.mock import MagicMock, patch

from ljpa_reworked.services.harness.harness_server import (
    HarnessRequest,
    agy_stream_generator,
    run_harness,
)


def test_harness_request_model_defaults_and_extensions():
    req = HarnessRequest(
        prompt_file="/app/prompts/harness_submit.md",
        vacancy_url="https://example.com/careers/123",
        resume_path="/app/resources/resumes/res.pdf",
    )
    assert req.prompt_file == "/app/prompts/harness_submit.md"
    assert req.vacancy_url == "https://example.com/careers/123"
    assert req.resume_path == "/app/resources/resumes/res.pdf"
    assert req.timeout == "8h"


def test_run_harness_goal_construction_untrusted_transport():
    req = HarnessRequest(
        prompt_file="/app/prompts/harness_submit.md",
        vacancy_url="https://example.com/apply?id=999",
        resume_path="/app/resources/resumes/resume_999.pdf",
    )

    with patch(
        "ljpa_reworked.services.harness.harness_server.agy_stream_generator"
    ) as mock_gen:
        mock_gen.return_value = (x for x in [])
        response = run_harness(req)

        assert response.media_type == "application/x-ndjson"
        mock_gen.assert_called_once()
        cmd = mock_gen.call_args.args[0]
        assert cmd[0] == "agy"
        assert "--dangerously-skip-permissions" in cmd
        assert "--print" in cmd
        goal_arg = next(arg for arg in cmd if arg.startswith("/goal"))
        assert "/app/prompts/harness_submit.md" in goal_arg
        assert "UNTRUSTED_VACANCY_URL: https://example.com/apply?id=999" in goal_arg
        assert (
            "UNTRUSTED_RESUME_PATH: /app/resources/resumes/resume_999.pdf" in goal_arg
        )


def test_run_harness_with_conversation_id_adds_conversation_flag():
    req = HarnessRequest(
        prompt_file="/app/prompts/harness_save_site_skill.md",
        conversation_id="conv-12345-xyz",
    )

    with patch(
        "ljpa_reworked.services.harness.harness_server.agy_stream_generator"
    ) as mock_gen:
        mock_gen.return_value = (x for x in [])
        response = run_harness(req)

        assert response.media_type == "application/x-ndjson"
        mock_gen.assert_called_once()
        cmd = mock_gen.call_args.args[0]
        assert "--conversation" in cmd
        conv_idx = cmd.index("--conversation")
        assert cmd[conv_idx + 1] == "conv-12345-xyz"
        print_idx = cmd.index("--print")
        print_arg = cmd[print_idx + 1]
        assert not print_arg.startswith("/goal")
        assert (
            "Execute the task defined in /app/prompts/harness_save_site_skill.md"
            in print_arg
        )


def test_agy_stream_generator_succeeds_after_normal_completion():
    mock_process = MagicMock()
    mock_process.stdout = ['{"event": "step", "text": "form submitted"}\n']
    mock_process.wait.return_value = None
    mock_process.returncode = 0

    with patch("subprocess.Popen", return_value=mock_process):
        lines = list(agy_stream_generator(["agy", "test"]))

    assert any('"status": "success"' in item for item in lines)


def test_agy_stream_generator_reports_process_failure():
    mock_process = MagicMock()
    mock_process.stdout = []
    mock_process.wait.return_value = None
    mock_process.returncode = 1

    with patch("subprocess.Popen", return_value=mock_process):
        lines = list(agy_stream_generator(["agy", "test"]))

    assert any('"status": "error"' in item for item in lines)
    assert any("exited with 1" in item for item in lines)


def test_run_harness_concurrency_serialization():
    import asyncio
    import threading
    import time

    from ljpa_reworked.services.harness.harness_server import harness_lock

    req = HarnessRequest(prompt_file="/app/prompts/harness_scraper.md")
    active_count = 0
    max_concurrent = 0

    def mock_popen(cmd, **kwargs):
        nonlocal active_count, max_concurrent
        active_count += 1
        if active_count > max_concurrent:
            max_concurrent = active_count

        mock_proc = MagicMock()
        time.sleep(0.05)
        mock_proc.stdout = ['{"event": "result", "result": {"status": "SUCCESS"}}\n']
        mock_proc.poll.return_value = 0
        active_count -= 1
        return mock_proc

    with patch("subprocess.Popen", side_effect=mock_popen):
        results = []

        def worker():
            resp = run_harness(req)

            async def _collect():
                return [line async for line in resp.body_iterator]

            lines = asyncio.run(_collect())
            results.append((resp, lines))

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(results) == 2
        for resp, _lines in results:
            assert resp.media_type == "application/x-ndjson"

    assert max_concurrent == 1
    assert harness_lock.locked() is False
