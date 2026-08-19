import json
import logging
import os
import sys

try:
    from mcp.server import MCPServer as ServerClass
except ImportError:
    from mcp.server.fastmcp import FastMCP as ServerClass

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("browser_use_mcp")

app = ServerClass("browser_use")


def get_llm():
    """Build the ChatOpenAI client strictly using LLM_BASE_URL, LLM_API_KEY, and BROWSER_USE_MODEL.

    Strict isolation guarantee: BROWSER_USE_MODEL must be used, NEVER LLM_MODEL.
    """
    from langchain_openai import ChatOpenAI

    base_url = os.environ.get("LLM_BASE_URL", "http://localhost:8000/v1")
    api_key = os.environ.get("LLM_API_KEY", "dummy_key")
    model = os.environ.get("BROWSER_USE_MODEL", "free-tier")

    logger.info(f"Initializing Browser Use LLM: model={model}, base_url={base_url}")
    return ChatOpenAI(
        model=model,
        openai_api_base=base_url,
        openai_api_key=api_key,
        temperature=0.0,
    )


def get_browser():
    """Connect to the shared CloakBrowser/Chromium instance over CDP."""
    from browser_use import Browser

    cdp_url = os.environ.get("CDP_URL", "http://cloak-browser:9222")
    logger.info(f"Connecting Browser Use to CDP endpoint: {cdp_url}")
    return Browser(cdp_url=cdp_url)


async def execute_browser_task(task: str, max_steps: int = 25) -> str:
    """Execute autonomous browser goal using Browser Use and return structured JSON."""
    from browser_use import Agent

    llm = get_llm()
    browser = get_browser()
    agent = Agent(
        task=task,
        llm=llm,
        browser=browser,
    )
    history = await agent.run(max_steps=max_steps)

    result_text = history.final_result() or "Task completed"
    errors = history.errors()

    report = {
        "status": "success" if not errors else "completed_with_errors",
        "result": result_text,
        "errors": errors if errors else None,
        "total_steps": len(history.history) if hasattr(history, "history") else 0,
    }
    return json.dumps(report, indent=2)


@app.tool()
async def run_browser_task(task: str, max_steps: int = 25) -> str:
    """Execute a high-level autonomous browser task using Browser Use and return a structured execution report."""
    return await execute_browser_task(task, max_steps=max_steps)


@app.tool()
async def browse_url(url: str, task: str) -> str:
    """Navigate to a target URL and perform a focused extraction or interaction task."""
    full_task = f"Navigate to {url} and perform: {task}"
    return await execute_browser_task(full_task)


if __name__ == "__main__":
    app.run(transport="stdio")
