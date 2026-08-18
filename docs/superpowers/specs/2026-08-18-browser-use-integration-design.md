# Browser Use Integration Design Specification

## 1. Overview & Objective
This specification details the integration of **Browser Use** into the existing Docker environment for `antigravity-cli`, exposing it to Google Antigravity as an MCP server.

Antigravity operates as the top-level orchestration and decision-making agent ("what to do"), while Browser Use operates as the autonomous browser execution layer ("how to navigate, interact, and extract").

---

## 2. Browser Responsibility & Interaction Model

```text
Antigravity
    |
    | (Decides WHAT to do, provides high-level goal & constraints)
    v
Browser Use MCP Server (`browser-use`)
    |
    | (Decides HOW to navigate, fill forms, handle popups, extract data)
    v
Browser Use Agent (powered by ChatOpenAI at LLM_BASE_URL with BROWSER_USE_MODEL)
    |
    | (CDP Connection to http://cloak-browser:9222)
    v
CloakBrowser / Chromium
```

### Delegation Pattern
* **Antigravity** issues concise, high-level browsing objectives (e.g., "Search LinkedIn posts for keywords X and return extracted vacancy details" or "Navigate to vacancy URL, complete the application using provided profile data, upload resume, and submit").
* **Browser Use** autonomously handles multi-step navigation, element interaction, dynamic DOM waits, dropdown selection, file upload, error handling, and form validation.
* **Return Value**: Browser Use returns a compact structured summary/execution report to Antigravity, preventing token bloat and eliminating low-level DOM micromanagement.

---

## 3. Environment & LLM Configuration Isolation

Browser Use must be strictly isolated from `LLM_MODEL`:

| Target Component | Environment Variable | Expected Value / Behavior |
| :--- | :--- | :--- |
| **Browser Use LLM Base URL** | `LLM_BASE_URL` | e.g. `http://XXX/v1` (OpenAI-compatible) |
| **Browser Use API Key** | `LLM_API_KEY` | Provided API key |
| **Browser Use Model** | `BROWSER_USE_MODEL` | `free-tier` (Strictly NEVER `LLM_MODEL`) |
| **Antigravity / Other Services** | `LLM_MODEL` | `gemini/gemini-3.5-flash-lite` (Unchanged) |
| **Browser CDP Endpoint** | `CDP_URL` | `http://cloak-browser:9222` |

---

## 4. Architecture & Components

### 4.1 MCP Server Adapter (`src/ljpa_reworked/services/docker/browser_use_mcp.py`)
A standalone Python MCP server script running inside the `antigravity-cli` container:
- Reads `LLM_BASE_URL`, `LLM_API_KEY`, `BROWSER_USE_MODEL` (default: `free-tier`), and `CDP_URL`.
- Configures `langchain_openai.ChatOpenAI` pointing to `LLM_BASE_URL`.
- Configures `browser_use.Browser(cdp_url=CDP_URL)` to reuse the existing CloakBrowser instance.
- Exposes tools via MCP (using FastMCP / `mcp.server.fastmcp`):
  - `run_browser_agent(task: str, max_steps: int = 25) -> str`: Executes an autonomous browser goal and returns the structured final outcome.
  - `browse_url(url: str, task: str) -> str`: Quick navigation and inspection helper.

### 4.2 Docker Configuration Updates
- **`Dockerfile.antigravity`**:
  - Install `browser-use`, `langchain-openai`, and necessary runtime dependencies via `pip`.
  - Copy `browser_use_mcp.py` to `/home/agent/.local/lib/browser_use_mcp.py`.
  - Update default `mcp_config.json` to register `browser_use`:
    ```json
    "browser_use": {
      "command": "python3",
      "args": ["/home/agent/.local/lib/browser_use_mcp.py"]
    }
    ```
- **`compose.yml` & `.env.example`**:
  - Expose `BROWSER_USE_MODEL=${BROWSER_USE_MODEL:-free-tier}` to `antigravity-cli`.

---

## 5. Harness Prompts Migration & Lifecycle

### 5.1 Backups
Before modifying prompt files, exact copies are created in:
- `prompts/backups/browser-use-migration/harness_scraper.md`
- `prompts/backups/browser-use-migration/harness_submit.md`
- `prompts/backups/browser-use-migration/harness_save_site_skill.md`

### 5.2 Updated Prompt Semantics
1. **`prompts/harness_scraper.md`**:
   - Delegates post searching, "See more" expansion, post content extraction, and external URL unwrapping to Browser Use MCP goals.
   - Retains candidate profile ingestion, 3-pass search strategy, evaluation gates (A-E), deduplication, 8-line standardized summary, and atomic database publishing (`/runtime/workspace/app.db.work` -> `/runtime/harness-scraper/app.db`).
2. **`prompts/harness_submit.md`**:
   - Delegates complete application workflows (form filling, dropdowns, resume attachment, modal handling, submit click, and confirmation check) to Browser Use MCP as a high-level task.
   - Enforces strict single-vacancy scope, profile-only sourcing (`/inputs/resources/profile.md`), credential vaulting (`/runtime/workspace/credentials.json`), IMAP OTP verification, and strict database prohibition.
3. **`prompts/harness_save_site_skill.md`**:
   - Distills reproducible site mechanics (ATS identity, navigation shortcuts, stable field patterns, file upload triggers) learned during Browser Use execution into `/runtime/workspace/<site>/SKILL.md`.
   - Strictly prohibits saving raw DOM step-by-step dumps, credentials, personal profile data, or temporary session state.
   - Maintains skill reuse lifecycle (try skill -> fallback to improvisation -> update skill).

---

## 6. Verification Plan
1. **Prompt Backups Verification**: Confirm directory and exact content matches.
2. **Static Config Check**: Confirm MCP JSON valid and `BROWSER_USE_MODEL` isolated.
3. **Container Build & Run**: Build `Dockerfile.antigravity` and confirm clean startup.
4. **Browser Use MCP Smoke Test**: Launch `browser_use_mcp.py` / call tool over MCP to verify connection to `LLM_BASE_URL` with `BROWSER_USE_MODEL=free-tier` and browser navigation over `CDP_URL`.
