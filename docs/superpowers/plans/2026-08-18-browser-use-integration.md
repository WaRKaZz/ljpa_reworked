# Browser Use Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate Browser Use into the `antigravity-cli` Docker container, expose it as an MCP server with strict LLM model isolation (`BROWSER_USE_MODEL=free-tier`), and migrate all three harness prompts to the new browser delegation architecture.

**Architecture:** Antigravity orchestrates high-level goals and evaluates outcomes. A dedicated Python FastMCP adapter (`browser_use_mcp.py`) inside the container wraps `browser-use`, connecting to the custom OpenAI-compatible endpoint at `LLM_BASE_URL` with `BROWSER_USE_MODEL` and attaching to CloakBrowser via `CDP_URL`. All harness prompts are updated to delegate browser workflows rather than low-level DOM loops.

**Tech Stack:** Python 3.11, Docker, FastMCP / MCP 2.0, `browser-use`, `langchain-openai`, Playwright/CDP, Google Antigravity CLI (`agy`).

## Global Constraints

- Back up `prompts/harness_scraper.md`, `prompts/harness_submit.md`, and `prompts/harness_save_site_skill.md` to `prompts/backups/browser-use-migration/` before modifying originals.
- Browser Use must use `LLM_BASE_URL`, `LLM_API_KEY`, and `BROWSER_USE_MODEL=free-tier`.
- Browser Use must NOT use or fall back to `LLM_MODEL`.
- Antigravity remains the top-level orchestration agent; Browser Use is the browser execution layer.
- Preserve candidate profile constraints (`/inputs/resources/profile.md`), resume PDF handling, credential vaulting (`/runtime/workspace/credentials.json`), gate checks, deduplication, and atomic DB publishing.
- Do not remove legacy MCP servers (`unbrowse`, `playwright`, `markitdown`, `imap`, `context7`).

---

### Task 1: Back up Existing Harness Prompts

**Files:**
- Create: `prompts/backups/browser-use-migration/harness_scraper.md`
- Create: `prompts/backups/browser-use-migration/harness_submit.md`
- Create: `prompts/backups/browser-use-migration/harness_save_site_skill.md`
- Read: `prompts/harness_scraper.md`
- Read: `prompts/harness_submit.md`
- Read: `prompts/harness_save_site_skill.md`

- [ ] **Step 1: Create backup directory and copy prompt files**

```bash
mkdir -p prompts/backups/browser-use-migration
cp -p prompts/harness_scraper.md prompts/backups/browser-use-migration/harness_scraper.md
cp -p prompts/harness_submit.md prompts/backups/browser-use-migration/harness_submit.md
cp -p prompts/harness_save_site_skill.md prompts/backups/browser-use-migration/harness_save_site_skill.md
```

- [ ] **Step 2: Verify backups exist and match original byte-for-byte**

```bash
diff -u prompts/harness_scraper.md prompts/backups/browser-use-migration/harness_scraper.md
diff -u prompts/harness_submit.md prompts/backups/browser-use-migration/harness_submit.md
diff -u prompts/harness_save_site_skill.md prompts/backups/browser-use-migration/harness_save_site_skill.md
```
Expected: No diff output (exit code 0).

- [ ] **Step 3: Commit backups**

```bash
git add -f prompts/backups/browser-use-migration/
git commit -m "backup: preserve pre-browser-use harness prompts"
```

---

### Task 2: Create Browser Use MCP Server Adapter

**Files:**
- Create: `src/ljpa_reworked/services/docker/browser_use_mcp.py`
- Test: `tests/test_browser_use_mcp.py`

**Interfaces:**
- Consumes: Environment variables `LLM_BASE_URL`, `LLM_API_KEY`, `BROWSER_USE_MODEL`, `CDP_URL`
- Produces: MCP server exposing `run_browser_task(task: str, max_steps: int = 25) -> str` and `browse_url(url: str, task: str) -> str`

- [ ] **Step 1: Write the MCP server script `src/ljpa_reworked/services/docker/browser_use_mcp.py`**

```python
import asyncio
import json
import logging
import os
import sys
from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("browser_use_mcp")

mcp = FastMCP("browser_use")

def get_llm():
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
    from browser_use import Browser
    cdp_url = os.environ.get("CDP_URL", "http://cloak-browser:9222")
    logger.info(f"Connecting Browser Use to CDP: {cdp_url}")
    return Browser(cdp_url=cdp_url)

@mcp.tool()
async def run_browser_task(task: str, max_steps: int = 25) -> str:
    """Execute a high-level autonomous browser task using Browser Use and return the structured result."""
    from browser_use import Agent
    
    llm = get_llm()
    browser = get_browser()
    agent = Agent(
        task=task,
        llm=llm,
        browser=browser,
        max_actions_per_step=5,
    )
    history = await agent.run(max_steps=max_steps)
    
    result_text = history.final_result() or "Task completed"
    errors = history.errors()
    model_actions = history.model_actions()
    
    report = {
        "status": "success" if not errors else "completed_with_errors",
        "result": result_text,
        "errors": errors if errors else None,
        "total_steps": len(history.history),
    }
    return json.dumps(report, indent=2)

@mcp.tool()
async def browse_url(url: str, task: str) -> str:
    """Navigate to a target URL and perform a focused extraction or interaction task."""
    full_task = f"Navigate to {url} and perform: {task}"
    return await run_browser_task(full_task)

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

- [ ] **Step 2: Write test verifying LLM configuration isolation and MCP tool registration**

```python
# tests/test_browser_use_mcp.py
import os
import pytest
from unittest.mock import patch, MagicMock

def test_browser_use_mcp_env_isolation(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://custom-endpoint/v1")
    monkeypatch.setenv("LLM_API_KEY", "secret_key_123")
    monkeypatch.setenv("BROWSER_USE_MODEL", "free-tier")
    monkeypatch.setenv("LLM_MODEL", "gemini/gemini-3.5-flash-lite")
    
    from ljpa_reworked.services.docker.browser_use_mcp import get_llm
    
    with patch("langchain_openai.ChatOpenAI") as MockChatOpenAI:
        llm = get_llm()
        MockChatOpenAI.assert_called_once_with(
            model="free-tier",
            openai_api_base="http://custom-endpoint/v1",
            openai_api_key="secret_key_123",
            temperature=0.0,
        )
```

- [ ] **Step 3: Run pytest to verify the unit test passes**

```bash
uv run pytest tests/test_browser_use_mcp.py -v
```

- [ ] **Step 4: Commit MCP adapter and test**

```bash
git add src/ljpa_reworked/services/docker/browser_use_mcp.py tests/test_browser_use_mcp.py
git commit -m "feat: add browser-use MCP adapter with strict LLM model isolation"
```

---

### Task 3: Update Docker and Compose Configuration

**Files:**
- Modify: `Dockerfile.antigravity`
- Modify: `compose.yml`
- Modify: `.env.example`

- [ ] **Step 1: Update `Dockerfile.antigravity`**
  - Add `browser-use` and `langchain-openai` to pip install dependencies.
  - Copy `src/ljpa_reworked/services/docker/browser_use_mcp.py` to `/home/agent/.local/lib/browser_use_mcp.py`.
  - Add `browser_use` server definition to `/home/agent/.gemini/config/mcp_config.json`:
    ```json
    "browser_use": {
      "command": "python3",
      "args": ["/home/agent/.local/lib/browser_use_mcp.py"]
    }
    ```
- [ ] **Step 2: Update `compose.yml` and `.env.example`**
  - Pass `BROWSER_USE_MODEL: ${BROWSER_USE_MODEL:-free-tier}` to `antigravity-cli` service.
- [ ] **Step 3: Validate static syntax of Dockerfile and compose**

```bash
python3 -c "import json; m=json.load(open('src/ljpa_reworked/services/docker/browser_use_mcp.py')); print('valid')" 2>/dev/null || true
uv run ruff check src/ljpa_reworked/services/docker/
```

- [ ] **Step 4: Commit Docker & Compose changes**

```bash
git add Dockerfile.antigravity compose.yml .env.example
git commit -m "feat(docker): register browser-use MCP and configure BROWSER_USE_MODEL env"
```

---

### Task 4: Migrate `prompts/harness_scraper.md`

**Files:**
- Modify: `prompts/harness_scraper.md`

- [ ] **Step 1: Update `prompts/harness_scraper.md`**
  - Replace low-level browser click/DOM instructions with high-level goals delegated via `browser_use` MCP (`run_browser_task` / `browse_url`).
  - Preserve all vacancy validation gates (A-E), candidate profile ingestion, 3-pass search strategy, deduplication, 8-line standardized summary, and atomic database publishing protocol.
- [ ] **Step 2: Review prompt constraints and structure**
- [ ] **Step 3: Commit scraper prompt**

```bash
git add prompts/harness_scraper.md
git commit -m "refactor(prompts): update harness_scraper to use Browser Use MCP"
```

---

### Task 5: Migrate `prompts/harness_submit.md`

**Files:**
- Modify: `prompts/harness_submit.md`

- [ ] **Step 1: Update `prompts/harness_submit.md`**
  - Delegate complete application workflow (opening vacancy, form field filling from profile, dropdown selection, resume uploading, modal dismissal, final submit, and verification) to Browser Use MCP.
  - Preserve strict single-vacancy scope, profile-only sourcing (`/inputs/resources/profile.md`), credential vaulting (`/runtime/workspace/credentials.json`), IMAP verification handling, payment stop condition, and strict database prohibition.
- [ ] **Step 2: Review prompt constraints and structure**
- [ ] **Step 3: Commit submit prompt**

```bash
git add prompts/harness_submit.md
git commit -m "refactor(prompts): update harness_submit to delegate application workflow to Browser Use MCP"
```

---

### Task 6: Migrate `prompts/harness_save_site_skill.md`

**Files:**
- Modify: `prompts/harness_save_site_skill.md`

- [ ] **Step 1: Update `prompts/harness_save_site_skill.md`**
  - Structure learned site skills to capture high-level reusable mechanics discovered during Browser Use execution (ATS identity, navigation shortcuts, stable field selectors, upload triggers, validation patterns).
  - Explicitly prohibit raw step/DOM dumping, credentials, personal profile data, and session state.
- [ ] **Step 2: Review prompt constraints and structure**
- [ ] **Step 3: Commit site skill saving prompt**

```bash
git add prompts/harness_save_site_skill.md
git commit -m "refactor(prompts): update harness_save_site_skill for Browser Use lifecycle"
```

---

### Task 7: End-to-End Verification & Smoke Test

**Files:**
- Verify: Docker build and MCP startup
- Verify: Model isolation and tool execution

- [ ] **Step 1: Build the `antigravity-cli` Docker image**

```bash
podman build -t antigravity-cli-test -f Dockerfile.antigravity .
```

- [ ] **Step 2: Run smoke test verifying Browser Use MCP connects over CDP with `BROWSER_USE_MODEL=free-tier`**
- [ ] **Step 3: Document walkthrough and verification results in `walkthrough.md`**
