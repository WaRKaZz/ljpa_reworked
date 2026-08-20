# Design Spec: LinkedIn Scraper Self-Learning Skill Loop

**Date:** 2026-08-20  
**Status:** Approved

---

## 1. Overview & Goals

Enable an adaptive, self-learning skill loop for the Google Antigravity LinkedIn post scraper harness (`harness_scraper`), mirroring the proven architecture of `harness_submit` / `harness_save_site_skill`:
1. **Pre-flight Skill Consultation**: Before executing searches and extracting posts, the scraper harness inspects `/runtime/workspace/linkedin_posts_scraper/SKILL.md` (and `/runtime/workspace/README.md`) for reusable selectors, query patterns, and DOM navigation workflows.
2. **Graceful Fallback / Resilience**: If the existing skill advice is outdated, fails, or fails to find elements on the live LinkedIn page, the scraper ignores the skill and falls back to dynamic DOM exploration without aborting the run.
3. **Post-Scraping Skill Persistence (Second Pass)**: Upon successful scraping completion and database publication, a second harness pass runs bound to the original `conversation_id` using `/app/prompts/harness_save_scraper_skill.md`. It extracts technical lessons learned during the run and updates `/runtime/workspace/linkedin_posts_scraper/SKILL.md` and `/runtime/workspace/README.md`.

---

## 2. Architecture & Components

### 2.1 Prompt Contracts

#### 1. `prompts/harness_scraper.md` (Updated)
- Add section `0. PRE-FLIGHT SKILL DISCOVERY & ADAPTIVE EXECUTION`:
  - Read `/runtime/workspace/README.md` and `/runtime/workspace/linkedin_posts_scraper/SKILL.md` if present.
  - If valid instructions exist, prioritize documented shortcuts: search URL formats, filter buttons, post expansion selectors (e.g. "See more" triggers), redirect unwrapping mechanics, and modal dismissal patterns.
  - **Graceful Ignore Rule**: If any skill selector fails or LinkedIn layout changed, immediately bypass the skill and proceed with standard dynamic exploration.

#### 2. `prompts/harness_save_scraper_skill.md` (New)
- Dedicated prompt for persisting reusable scraper knowledge after the run.
- Tasks:
  1. Create or overwrite `/runtime/workspace/linkedin_posts_scraper/SKILL.md`.
  2. Register `/runtime/workspace/linkedin_posts_scraper/SKILL.md` in `/runtime/workspace/README.md`.
- Content to persist:
  - Technical selector strategies for post cards, post text, "See more" expansion buttons, external apply links.
  - Search query patterns and keyword filters that yielded high match scores.
  - Redirect handling and URL unwrapping mechanics.
  - Workarounds for LinkedIn DOM quirks, infinite scroll handling, and modal dismissals.
- Privacy Boundaries:
  - Strict prohibition against storing candidate profile facts, contact info, names, email credentials, or database records.
  - No database modifications.

---

### 2.2 Python Services & Orchestration

#### 1. `src/ljpa_reworked/services/harness_runner.py`
- Add `HarnessScraperResult` dataclass:
  - `completed: bool`
  - `conversation_id: str | None = None`
  - `tail_lines: list[str] = field(default_factory=list)`
  - Backwards-compatible `__eq__` and `__int__` supporting `result == 0` checks.
- Update `run_linkedin_harness(...) -> HarnessScraperResult`:
  - Extract `conversation_id` from streamed JSON events (`event.get("conversation_id")` or `event.get("result", {}).get("conversation_id")`).
  - Return `HarnessScraperResult(completed=True/False, conversation_id=cid, tail_lines=...)`.
- Add `harness_save_scraper_skill(conversation_id: str, prompt_file: str = "/app/prompts/harness_save_scraper_skill.md", timeout: str = "30m", api_url: str = ..., http_timeout: float | None = None) -> int`:
  - Dispatches second pass AGY request with `req.conversation_id` and `prompt_file`.
  - Verifies skill activity (`SKILL.md`, `README.md`) in streamed response.

#### 2. `src/ljpa_reworked/main.py`
- Import `harness_save_scraper_skill`.
- In `run_linkedin_harness` call sites (`collect-harness` mode / `collect_and_submit_all` flow):
  - Check `result = run_linkedin_harness(...)`.
  - If `result.completed` and `result.conversation_id`:
    - Call `harness_save_scraper_skill(conversation_id=result.conversation_id)`.
    - Log success or capture exceptions with non-blocking error handling / Telegram notification.

---

## 3. Testing Strategy

1. **Unit Tests (`tests/test_harness_runner.py`)**:
   - `test_run_linkedin_harness_returns_scraper_result_with_conversation_id`: Verify result extraction from streaming JSON.
   - `test_harness_save_scraper_skill_success`: Verify second pass payload, URL, headers, and terminal status handling.
   - `test_harness_save_scraper_skill_failure`: Verify exception handling when conversation ID is missing or process errors out.
2. **Prompt Contract Tests (`tests/test_harness_terminal_protocol.py` or `tests/test_harness_submit_imap_skill.py`)**:
   - Verify `prompts/harness_save_scraper_skill.md` and `prompts/harness_scraper.md` adhere to expected skill paths (`/runtime/workspace/linkedin_posts_scraper/SKILL.md`, `README.md`).
3. **Integration / CLI Tests (`tests/test_url_submission_harness.py`, `tests/test_harness_runner.py`)**:
   - Verify `main.py` collector invocation invokes `harness_save_scraper_skill` on success.
