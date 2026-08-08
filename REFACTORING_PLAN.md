# Global Project Refactoring Plan

This document describes the plan for migrating from the legacy Selenium architecture to an automated agentic system based on Playwright, CloakBrowser, `antigravity-cli` (`agy` container), RenderCV, and SQLite.

## Stage 1: Dedicated Anti-Detect Browser Container & Session Auth

**Goal:** Establish a dedicated anti-detect browser service (`cloak-browser`) in Docker Compose exposing CDP port 9222 for automated CDP connection and persistent session storage (`resources/state.json`).

**Architecture & Container Topology:**
1. **Container 1: `cloak-browser` (Browser Sidecar)**
   * Built using `cloakhq/cloakbrowser:latest`. Priority rule: Always use existing pre-built Docker Hub images in `compose.yml`.
   * **Port Exposed:** `9222` — Remote CDP WebSocket (`http://cloak-browser:9222`) for agent connections.

2. **Container 2: `antigravity-cli` (`agy` Container & Harness Execution Engine)**
   * Runs the `antigravity-cli` environment, `agy` SDK, business logic, skills, MCP servers, and database operations.
   * Persistent volume mounts:
     - `./.gemini:/root/.gemini` — Stores skills, MCP servers (`mcp_config.json`), CLI settings, and authentication state across restarts.
     - `./.agents:/app/.agents` — Stores workspace-level skills and agent rules.
     - `./resources:/app/resources` — Stores session state (`resources/state.json`) and resume PDFs.
     - `./data:/app/data` — Persistent volume for SQLite database (`data/app.db`).
   * Connects to `cloak-browser` via CDP (`http://cloak-browser:9222`).

3. **Container 3: `linkedin-bot` (Production Application Container)**
   * Production container running the orchestrator script (`uv run src/ljpa_reworked/main.py`).

---

## Stage 2: Agent-Based Job Collection (Container Harnesses & agy / MCP Integration)

**Goal:** Implement automated job scraping pipelines (Harnesses) running inside the **`antigravity-cli` (`agy`)** container powered by the **Google Antigravity SDK (`agy`)** and **MCP Unbrowse / Playwright server** connected to `http://cloak-browser:9222`.

**Collection Pipelines (Harnesses inside `antigravity-cli` container):**
1. **Harness 1: LinkedIn Posts Scraper (`agy` Agent + MCP Unbrowse)**
   * **Execution Environment:** `antigravity-cli` container (`antigravity-cli-dev`) executed via `podman exec` running `agy --print --dangerously-skip-permissions "<prompt>"`.
   - **Logic & Prompting:** The `agy` agent receives candidate profile context (`resources/profile.md`), dynamically extracts and expands target candidate job titles across all matching potential roles based strictly on profile skills, and executes natural language web navigation commands via the MCP browser server.
   * **Execution:** Connects to `http://cloak-browser:9222`, loads `resources/state.json`, navigates to LinkedIn Posts, and extracts the **10 most recent posts with high skills matching**.
   * **Data Storage:** Maps fields and normalizes data into SQLAlchemy models, saving records directly to SQLite (`data/app.db`) across `Vacancy` and `LinkedinPost` tables.

2. **Harness 2: Official Job Postings via `python-jobspy`**
   * **Execution Environment:** `antigravity-cli` container.
   * **Logic:** API-level scraping of LinkedIn Jobs tab via `python-jobspy`.
   * **Execution:** Converts job records into SQLAlchemy objects, performs deduplication, and inserts entries into SQLite (`data/app.db`).

---

## Stage 3: JobSpy Adaptation & ETL Pipeline

**Goal:** Build a robust ETL mapping layer inside the `antigravity-cli` container to transform raw `python-jobspy` DataFrames into SQLite-compatible SQLAlchemy models.

---

## Stage 4: Code Review and QA (Isolated Unit & Integration Testing)

**Goal:** Ensure 100% test coverage and verify all components against the SQLite database and Playwright CDP architecture.

---

## Stage 5: Resume Generation Overhaul (RenderCV Integration)

**Goal:** Replace legacy HTML/Markdown resume generators with `RenderCV` for ATS-compliant PDF generation.

---

## Stage 6: Database and Models Adaptation (SQLite Schema)

**Goal:** Finalize SQLAlchemy ORM models and Alembic migrations for SQLite (`data/app.db`).

---

## Stage 7: Automated Web Application (Harness 3 - Web Fallback inside `antigravity-cli` container)

**Goal:** Automate job applications on external portals or LinkedIn Easy Apply when no recruiter email is available via `Harness 3` executing inside the `antigravity-cli` container.

---

## Stage 8: OpenAI-Compatible API Configuration

**Goal:** Standardize LLM calls across CrewAI and LiteLLM using an external OpenAI-compatible API endpoint.

---

## Stage 9: Container CLI & Maintenance Commands

**Goal:** Provide root-level convenience scripts for container and `antigravity-cli` operations.
