import asyncio

import mcp.types as types
import uvicorn
from markitdown import MarkItDown
from mcp.server import Server, ServerRequestContext


async def list_tools(
    _ctx: ServerRequestContext, _params: types.PaginatedRequestParams | None
) -> types.ListToolsResult:
    return types.ListToolsResult(
        tools=[
            types.Tool(
                name="convert_to_markdown",
                description="Convert a trusted local or remote resource URI to Markdown.",
                input_schema={
                    "type": "object",
                    "properties": {"uri": {"type": "string"}},
                    "required": ["uri"],
                },
            )
        ]
    )


async def call_tool(
    _ctx: ServerRequestContext, params: types.CallToolRequestParams
) -> types.CallToolResult:
    if params.name != "convert_to_markdown":
        raise ValueError(f"Unknown tool: {params.name}")
    uri = (params.arguments or {}).get("uri")
    if not isinstance(uri, str) or not uri:
        raise ValueError("uri must be a non-empty string")
    converted = await asyncio.to_thread(MarkItDown().convert_uri, uri)
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=converted.markdown)]
    )


app = Server("markitdown", on_list_tools=list_tools, on_call_tool=call_tool)

if __name__ == "__main__":
    uvicorn.run(
        app.streamable_http_app(host="markitdown-mcp"), host="0.0.0.0", port=3001
    )
