import asyncio

import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions

try:
    from markitdown import MarkItDown
except ImportError:  # pragma: no cover
    MarkItDown = None  # type: ignore

app = Server("markitdown")


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="convert_to_markdown",
            description="Convert a trusted local or remote resource URI to Markdown.",
            inputSchema={
                "type": "object",
                "properties": {"uri": {"type": "string"}},
                "required": ["uri"],
            },
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    if name != "convert_to_markdown":
        raise ValueError(f"Unknown tool: {name}")
    uri = (arguments or {}).get("uri")
    if not isinstance(uri, str) or not uri:
        raise ValueError("uri must be a non-empty string")

    if MarkItDown is None:
        raise RuntimeError("markitdown library is not installed")

    converted = await asyncio.to_thread(MarkItDown().convert_uri, uri)
    return [types.TextContent(type="text", text=converted.markdown)]


async def main() -> None:
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="markitdown",
                server_version="0.1.0",
                capabilities=app.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
