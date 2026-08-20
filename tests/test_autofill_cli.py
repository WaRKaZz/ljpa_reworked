import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ljpa_reworked.services.autofill.cli import run_autofill_cli
from ljpa_reworked.services.autofill.engine import AutofillResult, FieldFillRecord


@pytest.mark.asyncio
async def test_run_autofill_cli_success(tmp_path: Path, capsys):
    profile_file = tmp_path / "profile.md"
    profile_file.write_text(
        "# Candidate Profile\n**Name:** Ivan Danilov\n**Email:** ivan.danilov.wk@gmail.com\n",
        encoding="utf-8",
    )
    resume_file = tmp_path / "resume.pdf"
    resume_file.write_bytes(b"%PDF-1.4")

    mock_result = AutofillResult(
        status="complete",
        filled_count=2,
        filled=[
            FieldFillRecord(
                field="First Name",
                canonical="first_name",
                selector="#fname",
                value_source="profile.first_name",
            )
        ],
    )

    mock_page = MagicMock()
    mock_page.bring_to_front = AsyncMock()
    mock_context = MagicMock()
    mock_context.pages = [mock_page]
    mock_browser = MagicMock()
    mock_browser.contexts = [mock_context]
    mock_browser.close = AsyncMock()

    mock_playwright = MagicMock()
    mock_playwright.chromium.connect_over_cdp = AsyncMock(return_value=mock_browser)

    with (
        patch("ljpa_reworked.services.autofill.cli.async_playwright") as mock_pw_ctx,
        patch(
            "ljpa_reworked.services.autofill.cli.fill_form_batch",
            AsyncMock(return_value=mock_result),
        ),
    ):
        mock_pw_ctx.return_value.__aenter__.return_value = mock_playwright

        exit_code = await run_autofill_cli(
            profile_path=str(profile_file),
            resume_path=str(resume_file),
            cdp_url="http://mock-cdp:9222",
        )

        assert exit_code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["status"] == "complete"
        assert data["filled_count"] == 2
