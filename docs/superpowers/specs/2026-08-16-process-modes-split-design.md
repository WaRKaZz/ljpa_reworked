# Design Spec: Split Process Modes into URL Process and Email Process

## Summary
Refactor the LinkedIn Job Processing Automation (LJPA) execution modes by replacing monolithic/mixed process modes with three distinct, standalone runner modes and container services:
1. `collect` (`linkedin-bot-collect`): Scrapes and evaluates unrated vacancies.
2. `email_process` (`linkedin-bot-email-process`): Evaluates unreviewed vacancies, generates missing tailored resumes, and applies via email to all eligible vacancies (`score = rating - age_tax - visa_tax >= 50.0`) until the queue is exhausted.
3. `url_process` (`linkedin-bot-url-process`): Evaluates unreviewed vacancies, generates missing tailored resumes, and submits applications via URL harness iteratively as long as Gemini remaining quota is > 7% (`> 0.07`).

## Architecture & Components

### 1. `src/ljpa_reworked/main.py`
- Update CLI argument parser: `--mode` choices: `["collect", "url_process", "email_process"]` (default: `"collect"`). Remove deprecated `full` and `process` modes.
- `submit_top_email_vacancies(db, limit: int | None = None) -> int`:
  - When `limit is None`, process the entire `build_ranked_email_submission_queue(db)` (which enforces `score >= 50.0`).
  - For each vacancy: render PDF if missing, generate email with `crewai_generate_email`, send via `send_email`, mark status `submitted_via_email`.
- `submit_top_vacancies(db, limit: int | None = None) -> int`:
  - When `limit is None`, loop through `build_ranked_submission_queue(db)` (which enforces `score >= 50.0`).
  - Check `get_gemini_quota_remaining(HARNESS_API_URL) <= MINIMUM_GEMINI_5H_REMAINING` (0.07) before each submission. If quota <= 7%, stop immediately and exit.
  - For each vacancy: render PDF, submit via `harness_submit`, review with `crewai_review_submission_result`, save site skill, update status.
- Mode routing in `main(mode: str)`:
  - `"collect"`: Run LinkedIn harness + JobSpy discovery -> evaluate unrated vacancies -> exit.
  - `"email_process"`: Process unevaluated vacancies & missing resumes -> `submit_top_email_vacancies(db, limit=None)` -> exit.
  - `"url_process"`: Process unevaluated vacancies & missing resumes -> `submit_top_vacancies(db, limit=None)` -> exit.

### 2. `compose.yml`
- Remove legacy services `linkedin-bot-full` and `linkedin-bot-process`.
- Under `profiles: [ modes ]`, define three services:
  - `linkedin-bot-collect`: `command: uv run --no-dev python -m ljpa_reworked.main --mode collect`
  - `linkedin-bot-url-process`: `command: uv run --no-dev python -m ljpa_reworked.main --mode url_process`
  - `linkedin-bot-email-process`: `command: uv run --no-dev python -m ljpa_reworked.main --mode email_process`
- Base infrastructure (`cloak-browser`, `antigravity-cli`, `sqlite-ui`) remains unprofiled to start via `podman compose up -d`.

### 3. `README.md`
- Document the infrastructure startup (`podman compose up -d`).
- Document the three independent execution modes and their respective Podman Compose commands (`--profile modes up -d --no-deps <service>`).
- Document the stopping criteria:
  - `email_process` runs until all eligible vacancies with `score = rating - age_tax - visa_tax >= 50` have been submitted.
  - `url_process` runs iteratively as long as Gemini quota remaining > 7%.

### 4. Tests
- Update `tests/test_docker_compose_config.py` to assert the presence of `linkedin-bot-collect`, `linkedin-bot-url-process`, `linkedin-bot-email-process` and the absence of legacy `linkedin-bot-full` and `linkedin-bot-process`.
- Update `tests/test_main_modes.py` to test `--mode collect`, `--mode email_process`, and `--mode url_process`.

## Verification Plan
1. Unit tests: `uv run pytest tests/test_main_modes.py tests/test_docker_compose_config.py`
2. Full test suite: `uv run pytest`
3. Code formatting & linting: `uv run ruff check .` and `uv run ruff format .`
