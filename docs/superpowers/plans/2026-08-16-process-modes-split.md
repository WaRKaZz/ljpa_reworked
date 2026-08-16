# Split Process Modes into URL Process and Email Process Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the LJPA execution pipeline into three standalone modes: `collect`, `email_process` (which processes until all vacancies with score > 50 receive an email), and `url_process` (which submits URL vacancies iteratively as long as Gemini quota remaining > 7%).

**Architecture:** Python CLI (`src/ljpa_reworked/main.py`) handles mode routing and submission loop conditions. `compose.yml` provides three independent profile services (`linkedin-bot-collect`, `linkedin-bot-url-process`, `linkedin-bot-email-process`). `README.md` provides documentation for running base infrastructure and individual process containers.

**Tech Stack:** Python 3.12, SQLAlchemy, CrewAI, Podman/Docker Compose, pytest, ruff.

## Global Constraints
- `score = rating - (age_days * 1.5) - ((100 - visa_probability) / 2.2)` (enforced via `build_ranked_*_submission_queue` threshold >= 50.0).
- `email_process` runs until all queue items are processed.
- `url_process` runs until Gemini quota remaining <= 7% (0.07) or queue is exhausted.
- Podman Compose services for modes use `profiles: [ modes ]` and `userns_mode: keep-id`.

---

### Task 1: Update `main.py` CLI Modes and Submission Loops

**Files:**
- Modify: `src/ljpa_reworked/main.py`
- Test: `tests/test_main_modes.py`

**Interfaces:**
- `submit_top_email_vacancies(db: Session, limit: int | None = None) -> int`
- `submit_top_vacancies(db: Session, limit: int | None = None) -> int`
- `main(mode: str = "collect") -> int`

- [ ] **Step 1: Write the updated test cases in `tests/test_main_modes.py`**

```python
from unittest.mock import MagicMock, patch
from ljpa_reworked import main

def test_main_collect_mode_runs_discovery_and_evaluates():
    with (
        patch("ljpa_reworked.main.init_db") as init_db,
        patch("ljpa_reworked.main.SessionLocal") as session_local,
        patch("ljpa_reworked.main.run_linkedin_harness") as run_harness,
        patch("ljpa_reworked.main.JobSpyIntegrationService") as jobspy,
        patch("ljpa_reworked.main.evaluate_unrated_vacancies") as eval_vacancies,
        patch("ljpa_reworked.main.generate_missing_resumes") as gen_resumes,
        patch("ljpa_reworked.main.submit_top_email_vacancies") as submit_email,
        patch("ljpa_reworked.main.submit_top_vacancies") as submit_top,
    ):
        mock_db = MagicMock()
        session_local.return_value.__enter__.return_value = mock_db

        ret = main.main(mode="collect")
        assert ret == 0

        init_db.assert_called_once()
        run_harness.assert_called_once()
        jobspy.return_value.run.assert_called_once()
        eval_vacancies.assert_called_once_with(mock_db)
        gen_resumes.assert_not_called()
        submit_email.assert_not_called()
        submit_top.assert_not_called()

def test_main_email_process_mode_runs_eval_and_submits_all_emails():
    with (
        patch("ljpa_reworked.main.init_db") as init_db,
        patch("ljpa_reworked.main.SessionLocal") as session_local,
        patch("ljpa_reworked.main.run_linkedin_harness") as run_harness,
        patch("ljpa_reworked.main.JobSpyIntegrationService") as jobspy,
        patch("ljpa_reworked.main.process_unevaluated_vacancies") as process_vacancies,
        patch("ljpa_reworked.main.submit_top_email_vacancies", return_value=3) as submit_email,
        patch("ljpa_reworked.main.submit_top_vacancies") as submit_top,
    ):
        mock_db = MagicMock()
        session_local.return_value.__enter__.return_value = mock_db

        ret = main.main(mode="email_process")
        assert ret == 0

        init_db.assert_called_once()
        run_harness.assert_not_called()
        jobspy.assert_not_called()
        process_vacancies.assert_called_once_with(mock_db)
        submit_email.assert_called_once_with(mock_db, limit=None)
        submit_top.assert_not_called()

def test_main_url_process_mode_runs_eval_and_submits_urls():
    with (
        patch("ljpa_reworked.main.init_db") as init_db,
        patch("ljpa_reworked.main.SessionLocal") as session_local,
        patch("ljpa_reworked.main.run_linkedin_harness") as run_harness,
        patch("ljpa_reworked.main.JobSpyIntegrationService") as jobspy,
        patch("ljpa_reworked.main.process_unevaluated_vacancies") as process_vacancies,
        patch("ljpa_reworked.main.submit_top_email_vacancies") as submit_email,
        patch("ljpa_reworked.main.submit_top_vacancies", return_value=2) as submit_top,
    ):
        mock_db = MagicMock()
        session_local.return_value.__enter__.return_value = mock_db

        ret = main.main(mode="url_process")
        assert ret == 0

        init_db.assert_called_once()
        run_harness.assert_not_called()
        jobspy.assert_not_called()
        process_vacancies.assert_called_once_with(mock_db)
        submit_email.assert_not_called()
        submit_top.assert_called_once_with(mock_db, limit=None)
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/test_main_modes.py -v`

- [ ] **Step 3: Update `src/ljpa_reworked/main.py`**

Update `submit_top_email_vacancies`, `submit_top_vacancies`, `main`, and the argument parser to support `limit: int | None = None` and the modes `collect`, `email_process`, `url_process`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_main_modes.py -v`

- [ ] **Step 5: Commit changes**

```bash
git add src/ljpa_reworked/main.py tests/test_main_modes.py
git commit -m "feat: split main execution modes into collect, email_process, and url_process"
```

---

### Task 2: Update `compose.yml` and Compose Test Configuration

**Files:**
- Modify: `compose.yml`
- Test: `tests/test_docker_compose_config.py`

- [ ] **Step 1: Update `tests/test_docker_compose_config.py`**

Ensure `tests/test_docker_compose_config.py` expects `linkedin-bot-collect`, `linkedin-bot-url-process`, `linkedin-bot-email-process` and asserts removal of `linkedin-bot-full` and `linkedin-bot-process`.

- [ ] **Step 2: Run compose tests to verify failure**

Run: `uv run pytest tests/test_docker_compose_config.py -v`

- [ ] **Step 3: Modify `compose.yml`**

Replace `linkedin-bot-full` and `linkedin-bot-process` with `linkedin-bot-url-process` and `linkedin-bot-email-process` (each with `profiles: [ modes ]`).

- [ ] **Step 4: Run compose tests to verify pass**

Run: `uv run pytest tests/test_docker_compose_config.py -v`

- [ ] **Step 5: Commit changes**

```bash
git add compose.yml tests/test_docker_compose_config.py
git commit -m "feat: update compose services for url_process and email_process modes"
```

---

### Task 3: Update `README.md` Documentation

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update `README.md`**

Add clear instructions for starting base infrastructure (`podman compose up -d`) and the 3 distinct runner profiles:
- `podman compose --profile modes up -d --no-deps linkedin-bot-collect`
- `podman compose --profile modes up -d --no-deps linkedin-bot-email-process`
- `podman compose --profile modes up -d --no-deps linkedin-bot-url-process`
Explain the execution logic and stopping criteria for each mode.

- [ ] **Step 2: Commit changes**

```bash
git add README.md
git commit -m "docs: document collect, email_process, and url_process compose modes in README"
```

---

### Task 4: Run Full Test Suite and Linter

- [ ] **Step 1: Run linter and formatting**
Run: `uv run ruff check . && uv run ruff format .`

- [ ] **Step 2: Run full pytest suite**
Run: `uv run pytest`
