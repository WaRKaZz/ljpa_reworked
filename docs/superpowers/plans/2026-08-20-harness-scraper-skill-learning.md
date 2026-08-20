# LinkedIn Scraper Self-Learning Skill Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a self-learning skill loop for LinkedIn scraper harness (`harness_scraper`) that consults `/runtime/workspace/linkedin_posts_scraper/SKILL.md` before scraping, gracefully falls back if obsolete, and runs a second pass (`harness_save_scraper_skill.md`) after success to save/update the skill.

**Architecture:** 
- `prompts/harness_scraper.md` updated with pre-flight skill inspection and fallback rule.
- `prompts/harness_save_scraper_skill.md` created to guide AGY on updating `/runtime/workspace/linkedin_posts_scraper/SKILL.md` and `README.md`.
- `HarnessScraperResult` and `harness_save_scraper_skill` added to `src/ljpa_reworked/services/harness_runner.py`.
- `src/ljpa_reworked/main.py` updated to invoke `harness_save_scraper_skill` upon successful scraper run.

**Tech Stack:** Python 3.12, Google Antigravity CLI (`agy`), FastAPI/HTTP streaming, SQLite3, Pytest.

## Global Constraints

- Never store candidate personal data, passwords, OTPs, or database records in `SKILL.md` or `README.md`.
- Scraper harness operates strictly on `/runtime/workspace/app.db.work` and never modifies canonical database directly during scraping.
- `run_linkedin_harness` return value must preserve backward compatibility where `int(result) == 0` signifies success.

---

### Task 1: Update Scraper Main Prompt (`prompts/harness_scraper.md`)

**Files:**
- Modify: `prompts/harness_scraper.md`
- Test: `tests/test_harness_terminal_protocol.py`

**Interfaces:**
- Consumes: `/runtime/workspace/linkedin_posts_scraper/SKILL.md` (if exists) and `/runtime/workspace/README.md`.
- Produces: Instructions for agent to check skill, use working shortcuts, ignore if not helpful, and fallback to dynamic search.

- [ ] **Step 1: Write the failing test for prompt contract**
Add test in `tests/test_harness_terminal_protocol.py` verifying `prompts/harness_scraper.md` references `/runtime/workspace/linkedin_posts_scraper/SKILL.md` and adaptive fallback.

- [ ] **Step 2: Run test to verify it fails**
Run: `uv run pytest tests/test_harness_terminal_protocol.py -k test_harness_scraper_prompt_contract`
Expected: FAIL

- [ ] **Step 3: Update `prompts/harness_scraper.md`**
Add section `0. PRE-FLIGHT SKILL DISCOVERY & ADAPTIVE EXECUTION` instructing the agent to read `/runtime/workspace/linkedin_posts_scraper/SKILL.md` and `/runtime/workspace/README.md`, reuse working patterns, and ignore if unhelpful.

- [ ] **Step 4: Run test to verify it passes**
Run: `uv run pytest tests/test_harness_terminal_protocol.py -k test_harness_scraper_prompt_contract`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add prompts/harness_scraper.md tests/test_harness_terminal_protocol.py
git commit -m "feat(scraper): add pre-flight skill discovery and adaptive fallback instructions to scraper prompt"
```

---

### Task 2: Create Scraper Skill Saving Prompt (`prompts/harness_save_scraper_skill.md`)

**Files:**
- Create: `prompts/harness_save_scraper_skill.md`
- Test: `tests/test_harness_submit_imap_skill.py`

**Interfaces:**
- Consumes: Scraper session context via conversation ID.
- Produces: Updated `/runtime/workspace/linkedin_posts_scraper/SKILL.md` and `/runtime/workspace/README.md`.

- [ ] **Step 1: Write the failing test for save prompt contract**
Add test in `tests/test_harness_submit_imap_skill.py` checking `prompts/harness_save_scraper_skill.md` exists and contains required boundaries.

- [ ] **Step 2: Run test to verify it fails**
Run: `uv run pytest tests/test_harness_submit_imap_skill.py -k test_harness_save_scraper_skill_prompt_contracts`
Expected: FAIL

- [ ] **Step 3: Create `prompts/harness_save_scraper_skill.md`**
Implement the prompt guiding the agent to analyze the conversation and persist technical selectors, queries, and navigation workflows to `/runtime/workspace/linkedin_posts_scraper/SKILL.md`.

- [ ] **Step 4: Run test to verify it passes**
Run: `uv run pytest tests/test_harness_submit_imap_skill.py -k test_harness_save_scraper_skill_prompt_contracts`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add prompts/harness_save_scraper_skill.md tests/test_harness_submit_imap_skill.py
git commit -m "feat(scraper): add harness_save_scraper_skill prompt for post-scraping knowledge persistence"
```

---

### Task 3: Implement `HarnessScraperResult` and `harness_save_scraper_skill` in `harness_runner.py`

**Files:**
- Modify: `src/ljpa_reworked/services/harness_runner.py`
- Test: `tests/test_harness_runner.py`

**Interfaces:**
- Produces: `HarnessScraperResult(completed: bool, conversation_id: str | None, tail_lines: list[str])`, `run_linkedin_harness(...) -> HarnessScraperResult`, `harness_save_scraper_skill(conversation_id: str, ...)`

- [ ] **Step 1: Write the failing tests**
In `tests/test_harness_runner.py`:
- `test_run_linkedin_harness_captures_conversation_id`
- `test_harness_save_scraper_skill_success`
- `test_harness_save_scraper_skill_requires_conversation_id`

- [ ] **Step 2: Run test to verify it fails**
Run: `uv run pytest tests/test_harness_runner.py -k "test_run_linkedin_harness_captures_conversation_id or test_harness_save_scraper_skill"`
Expected: FAIL

- [ ] **Step 3: Implement `HarnessScraperResult` and `harness_save_scraper_skill`**
Update `src/ljpa_reworked/services/harness_runner.py` to parse `conversation_id`, return `HarnessScraperResult`, and define `harness_save_scraper_skill`.

- [ ] **Step 4: Run tests to verify they pass**
Run: `uv run pytest tests/test_harness_runner.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add src/ljpa_reworked/services/harness_runner.py tests/test_harness_runner.py
git commit -m "feat(harness): return HarnessScraperResult with conversation_id and add harness_save_scraper_skill"
```

---

### Task 4: Integrate Scraper Skill Saving in `main.py` Orchestrator

**Files:**
- Modify: `src/ljpa_reworked/main.py`
- Test: `tests/test_submission_result_review.py` or new test in `tests/test_harness_runner.py`

**Interfaces:**
- Consumes: `run_linkedin_harness`, `harness_save_scraper_skill`.

- [ ] **Step 1: Write failing integration test**
Add test verifying that when `run_linkedin_harness` succeeds in `main.py`, `harness_save_scraper_skill` is called with the returned `conversation_id`.

- [ ] **Step 2: Run test to verify it fails**
Run: `uv run pytest tests/test_harness_runner.py -k test_main_collect_harness_triggers_save_scraper_skill`
Expected: FAIL

- [ ] **Step 3: Update `main.py`**
In `main.py`, update the `collect-harness` mode and `run_linkedin_harness` invocation to call `harness_save_scraper_skill(conversation_id=res.conversation_id)` if `res.completed and res.conversation_id`.

- [ ] **Step 4: Run test to verify it passes**
Run: `uv run pytest tests/test_harness_runner.py -k test_main_collect_harness_triggers_save_scraper_skill`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add src/ljpa_reworked/main.py tests/test_harness_runner.py
git commit -m "feat(main): trigger harness_save_scraper_skill after successful linkedin discovery"
```

---

### Task 5: Full Verification & Prompt Backup Tests

**Files:**
- Modify/Update: `tests/test_prompt_backups.py` if needed
- Test: Full test suite (`uv run pytest`)

- [ ] **Step 1: Run full pytest suite**
Run: `uv run pytest`
Expected: 300+ passed, 0 failures, coverage >= 65%.

- [ ] **Step 2: Format and check code quality**
Run: `uv run ruff check .` and `uv run ruff format .`

- [ ] **Step 3: Final Commit**
```bash
git add .
git commit -m "chore: format and verify LinkedIn scraper self-learning skill loop"
```
