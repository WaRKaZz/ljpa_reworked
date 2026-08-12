from unittest.mock import MagicMock, patch

import pytest

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


@pytest.mark.asyncio
async def test_run_harness_goal_construction_untrusted_transport():
    req = HarnessRequest(
        prompt_file="/app/prompts/harness_submit.md",
        vacancy_url="https://example.com/apply?id=999",
        resume_path="/app/resources/resumes/resume_999.pdf",
    )

    with patch("ljpa_reworked.services.harness.harness_server.agy_stream_generator") as mock_gen:
        mock_gen.return_value = (x for x in [])
        response = await run_harness(req)

        assert response.media_type == "application/x-ndjson"
        mock_gen.assert_called_once()
        cmd = mock_gen.call_args.args[0]
        assert cmd[0] == "agy"
        assert "--dangerously-skip-permissions" in cmd
        assert "--print" in cmd
        goal_arg = next(arg for arg in cmd if arg.startswith("/goal"))
        assert "/app/prompts/harness_submit.md" in goal_arg
        assert "UNTRUSTED_VACANCY_URL: https://example.com/apply?id=999" in goal_arg
        assert "UNTRUSTED_RESUME_PATH: /app/resources/resumes/resume_999.pdf" in goal_arg


@pytest.mark.asyncio
async def test_agy_stream_generator_success_on_confirmed_submission():
    mock_process = MagicMock()
    mock_process.stdout = [
        '{"event": "step", "text": "filling form"}\n',
        '{"status": "confirmed_submitted", "vacancy_url": "https://example.com/apply"}\n',
    ]
    mock_process.wait.return_value = None
    mock_process.returncode = 0

    with patch("subprocess.Popen", return_value=mock_process):
        lines = []
        async for line in agy_stream_generator(["agy", "test"], require_confirmation=True):
            lines.append(line)

        assert any("confirmed_submitted" in item for item in lines)
        assert any('"status": "success"' in item for item in lines)


@pytest.mark.asyncio
async def test_agy_stream_generator_failure_when_confirmation_missing():
    mock_process = MagicMock()
    mock_process.stdout = [
        '{"event": "step", "text": "form completed but no confirmation page"}\n'
    ]
    mock_process.wait.return_value = None
    mock_process.returncode = 0

    with patch("subprocess.Popen", return_value=mock_process):
        lines = []
        async for line in agy_stream_generator(["agy", "test"], require_confirmation=True):
            lines.append(line)

        assert any('"status": "error"' in item for item in lines)
        assert any("without confirmed submission" in item for item in lines)

