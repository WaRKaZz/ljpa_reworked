from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import ljpa_reworked.services.docker.markitdown_mcp as markitdown_mcp
from ljpa_reworked.services.docker.markitdown_mcp import (
    app,
    call_tool,
    list_tools,
    main,
)


@pytest.mark.asyncio
async def test_markitdown_mcp_list_tools():
    tools = await list_tools()
    tool_names = [t.name for t in tools]
    assert "convert_to_markdown" in tool_names


@pytest.mark.asyncio
async def test_markitdown_mcp_call_tool(tmp_path):
    sample = tmp_path / "sample.txt"
    sample.write_text("Hello MCP MarkItDown", encoding="utf-8")

    mock_instance = MagicMock()
    mock_converted = MagicMock()
    mock_converted.markdown = "# Converted Markdown Content"
    mock_instance.convert_uri.return_value = mock_converted

    with patch.object(markitdown_mcp, "MarkItDown", return_value=mock_instance):
        result = await call_tool("convert_to_markdown", {"uri": str(sample)})
        assert len(result) == 1
        assert result[0].text == "# Converted Markdown Content"


@pytest.mark.asyncio
async def test_markitdown_mcp_call_tool_not_installed():
    with patch.object(markitdown_mcp, "MarkItDown", None):
        with pytest.raises(RuntimeError, match="markitdown library is not installed"):
            await call_tool("convert_to_markdown", {"uri": "/tmp/test.txt"})


@pytest.mark.asyncio
async def test_markitdown_mcp_call_tool_invalid_name():
    with pytest.raises(ValueError, match="Unknown tool"):
        await call_tool("unknown_tool", {"uri": "something"})


@pytest.mark.asyncio
async def test_markitdown_mcp_call_tool_empty_uri():
    with pytest.raises(ValueError, match="uri must be a non-empty string"):
        await call_tool("convert_to_markdown", {"uri": ""})


@pytest.mark.asyncio
async def test_markitdown_mcp_main():
    with patch("mcp.server.stdio.stdio_server") as mock_stdio:
        mock_stdio.return_value.__aenter__.return_value = (MagicMock(), MagicMock())
        with patch.object(app, "run", new_callable=AsyncMock) as mock_run:
            await main()
            assert mock_run.called
