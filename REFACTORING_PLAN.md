# Global Project Refactoring Plan

> **Runtime decision:** Podman Compose. `linkedin-bot` is the application container; its Python calls the isolated `antigravity-cli` runtime API for agent tasks. Development TODOs are implemented separately with direct host `agy` on `id-laptop`. `main.py` intentionally runs the complete pipeline. The pipeline has no standalone JobSpy mode: it runs sequentially after LinkedIn-post collection and before review.

## Current baseline — verified 2026-08-10

- Canonical SQLite database: `data/app.db`; it is recreated by SQLAlchemy `init_db()` when a fresh baseline is required. Alembic is removed.
- `resources/app.db` was an empty obsolete artifact and was removed.
- The canonical DB passed `PRAGMA integrity_check` after fresh-schema recreation; current verified count is 12 `created` vacancies.
- LinkedIn login/session bootstrap is implemented and operational; `data/state.json` remains its canonical ignored state path.
- LLM gateway: OpenAI-compatible `http://id-vps:20128/v1`, configured by `LLM_BASE_URL`.
- Quality baseline: `uv run pytest -q`, `uv run --extra dev ruff check src tests`, `uv run python -m compileall -q src`, and `podman compose config -q`.
- Pipeline components: LinkedIn Post Vacancy Collector collects LinkedIn post vacancies; JobSpy Vacancy Search saves JobSpy vacancies; Vacancy Review and Resume Generation follows; Application Harness is planned and not yet verified.

## Stage 1: LinkedIn Post Vacancy Collector — **complete / verified by operator**

**Goal:** Keep agent work in `antigravity-cli`, not inside the application container.

### Completed

- `antigravity-cli` is a distinct runtime service with `agy`, MCP tools and `harness_server.py`.
- Development TODOs are executed separately with direct host `agy`, not through this runtime service.
- `linkedin-bot` remains the production application container.
- Harness runner sends requests to `http://antigravity-cli:8080/run-harness` over the internal network.
- `main.py` calls the full pipeline by design.

### Completed

- Harness 1 reads candidate material, uses the canonical ignored `data/state.json` session state, and collects final `Vacancy` records directly.
- The obsolete `LinkedinPost` raw-post pipeline and post-review crew are removed.
- `prompts/harness_scraper.md` requires full original-post review, structured vacancy summaries, verified submission contacts, per-run URL write deduplication, workspace DB staging, integrity checks, and atomic canonical-DB replacement.

### Follow-up maintenance

- Keep its prompt, schema terminology, and tests aligned when the collector changes. This is maintenance, not an open implementation stage.

## Stage 1A: Direct LinkedIn vacancies and fresh database baseline — **complete / verified by operator**

**Goal:** Harness 1 validates fully opened LinkedIn posts and publishes final vacancies through an audited workspace DB copy; no raw-post table or post-review crew remains.

### Completed

- Direct `Vacancy` collection is implemented; raw LinkedIn post storage and review-crew conversion are removed.
- New source rows are `created`; the exact matching `submit_url` may refresh source-owned fields as `updated`.
- The collector never treats a search card, post permalink, profile, feed, or search URL as a submission contact.
- The collector stores a concise structured vacancy summary rather than raw LinkedIn post text.
- Runtime agent artifacts use the persistent `/workspace` volume and document retained files in `/workspace/README.md`.

## Stage 1B: Vacancy submission contact model and fresh database — **complete / verified by operator**

**Goal:** Replace legacy `Vacancy.credentials` and `Vacancy.url` with explicit nullable `submit_email` and `submit_url`, enforce database-level contact check constraint, and replace Alembic with explicit SQLAlchemy metadata bootstrap (`init_db()`).

### Completed

- Removed legacy fields `credentials` and `url` from `Vacancy` model and Pydantic schemas.
- Added explicit nullable `submit_email` and `submit_url` with SQLite database-level `CHECK` constraint `(submit_email IS NOT NULL AND TRIM(submit_email) != '') OR (submit_url IS NOT NULL AND TRIM(submit_url) != '')`.
- Pydantic models normalize blank strings to `None`, validate email syntax, and enforce at least one contact method.
- Updated Harness prompt, JobSpy mapping, Crew task templates, operations, and main workflow to use `submit_email` and `submit_url`.
- Removed Alembic configuration and dependency; added explicit SQLAlchemy metadata bootstrap `init_db()`.
- Backed up canonical database, recreated fresh `data/app.db` via `init_db()`, and verified with `PRAGMA integrity_check`.


## Stage 2: JobSpy search and ETL — **complete for unit scope**

**Goal:** Search JobSpy and save or refresh vacancies as Step 2, after LinkedIn harness collection and before review.

### Completed

- `JobSpyIntegrationService` generates profile-grounded CrewAI queries with a SHA-256 cache.
- Query contract validates source, bounds, hash and normalized duplicate queries.
- A mismatched LLM profile hash fails without overwriting a valid cache.
- `submit_url` is the canonical JobSpy identity when present; email-only vacancies are allowed, and blank contact pairs are skipped.
- `VacancyStatus` replaced `Vacancy.processed`; lifecycle state is explicit and `submit_url` is unique when present.
- `JobSpyIntegrationService.run()` returns summary metrics for the Step-2 search.

### Constraint for future changes

- Do not create a fallback identity for URL-less rows unless JobSpy supplies a proven immutable source ID.

## Stage 3: QA gates — **complete / verified by operator**

**Goal:** Reliable gates, not an arbitrary 100% coverage target.

### Completed

- Unit and acceptance tests cover statuses, fresh metadata bootstrap, contact validation, `submit_url` upsert, sequential JobSpy integration, Compose structure, session paths, and LLM gateway construction.
- Stage 3.1 completed: Full test suite audited. 83 tests passing, 0 skipped. Removed 0-byte junk file `src/ljpa_reworked/test.py`, duplicate test `tests/test_stage1_e2e.py`, and moved `src/ljpa_reworked/tests/` into `tests/` with deterministic mocks for `SMTPClient` and `Telegram` services (preventing network calls and credential skips).
- `data/app.db` verified completely unmodified (SHA-256 hash match).
- `pytest`, Ruff, `compileall`, `git diff --check`, and `podman compose config -q` passed for the completed refactor.
- Fresh-schema bootstrap was verified with disposable SQLite databases before recreating canonical `data/app.db`.
- Stage 3.2 completed: `pytest-cov` added as a dev dependency. Measured baseline coverage for package `src/ljpa_reworked` excluding `**/__init__.py` and `src/ljpa_reworked/main.py` is 65.21%. Gate configured in `pyproject.toml` with `fail_under = 65` and terminal `term-missing` coverage report. 84 tests passing, 0 skipped. Added `test_pytest_coverage_gate_configured` in `tests/test_task7_acceptance_gates.py`.
- Operator confirms the remaining isolated-container checks and opt-in smoke-test work are complete; Stage 3 is recorded complete without altering canonical data or launching the external-effect pipeline.


## Stage 4: Resume generation with RenderCV — **in progress**

**Goal:** Replace legacy resume generation with RenderCV-produced ATS PDF output.

### 4A: ATS resume model audit — **complete / verified by operator**

1. Inventory of candidate input categories, vacancy, evaluator, `Resume`, and `ResumeCrewAI` fields against RenderCV ATS requirements (including optional links and languages representation) documented in `docs/stage-04a-resume-model-audit.md` without personal data or secrets.
2. Minimum required 4B schema additions identified: optional `location` & `linkedin_url` in personal info, `url`, `start_date`, `end_date` & `highlights` in projects, `issuer`, `date` & `url` in certifications, optional `rendered_at` on `Resume`, and verified languages representation (sufficient under `skills` JSON, optional dedicated `languages` list in 4B).
3. Audited Stage 4E cleanup metadata: corrected factual error regarding sent evidence—`Email.sent` is never set by the actual main send path, and `TelegramStatus.sent` records a vacancy notification rather than a sent resume. Verified that only `VacancyStatus.applied` is currently evidence of completed application submission; because its timestamp is absent (`Vacancy` lacks `updated_at` or submission timestamp), Stage 4E requires an explicit application/submission timestamp.
4. Updated focused unit test suite `tests/test_stage4a_resume_model_audit.py` protecting baseline model validation, DB operations, languages/links audit facts, and verified sent evidence properties.

### 4B: Resume model and schema — **complete / verified by operator**

1. Added the audited Stage 4A ATS fields to `PersonalInfoCrewAI` (`location`, `linkedin_url`), `ProjectCrewAI` (`url`, `start_date`, `end_date`, `highlights`), and `CertificationCrewAI` (`issuer`, `date`, `url`). Languages retained under `skills`.
2. Added nullable `Resume.rendered_at` and `Vacancy.applied_at` columns.
3. Implemented `confirm_email_application_submitted()` to stamp `Vacancy.applied_at` only after confirmed email send and transition to `applied`. Unconfirmed transitions leave `applied_at` unset (`None`).
4. Enforced fresh disposable SQLite schema boundary without touching canonical `data/app.db`.

### 4C: Profile-based evaluator, CrewAI data, and render smoke — **complete**

1. Replaced legacy CV PDF and URL scraping in resume evaluator and generator CrewAI prompts/code with local candidate source `resources/profile.md`. Retained `linkedin_url` strictly as an output field for RenderCV header display.
2. Minimized evaluator and generator YAML prompts to prevent long prompt overheads and ensure deterministic execution under 75 seconds per call.
3. Added `rendercv[full]` dependency and `render_resume_crewai_to_pdf` helper service in `src/ljpa_reworked/services/rendercv_helper.py` with `phonenumbers` validation for RenderCV compatibility.
4. Executed permitted real end-to-end smoke test using `resources/profile.md` and a synthetic vacancy through configured gateway: evaluator succeeded, generator produced valid `ResumeCrewAI`, RenderCV compiled a non-empty PDF under `/tmp`, verified non-zero size, and deleted the PDF afterwards.
5. All hermetic contract tests and real smoke tests passed (109 passed, 71.10% coverage).

### 4D: RenderCV output and one operator-reviewed PDF — **in progress**

1. **4D.1: Production persistence path — complete / verified by operator.** Replaced legacy `ResumeGenerator` call in `save_resume()` with `render_resume_crewai_to_pdf()`. Saves only a collision-safe relative filename under `RESOURCES_DIR/resumes/` and persists it with `Resume.rendered_at`. Atomically cleans up the generated PDF if rendering or DB creation fails and re-raises exceptions. Verified with hermetic unit tests using in-memory SQLite (113 passed, 78.95% coverage).
2. **4D.2: One operator-reviewed PDF — detailed-contract correction in progress.** The direct-profile replacement PDF was valid but rejected as too sparse. Strengthen evaluator/generator contracts for structured factual inclusion, detailed entries, categorized skills, and max-two-page layout with a minimum half-full secondary page. Restore from verified backup and create exactly one new evaluator+generator artifact for vacancy ID 1 after hermetic verification. Keep the backup and leave 4D.2 incomplete until Ivan visually accepts it. Do not submit, email, message, collect LinkedIn, run JobSpy, or run the full pipeline.

### 4E: Resume cleanup — **not started**

1. Delete generated resumes for vacancies sent more than two months ago.
2. Delete generated resumes that were never sent.
3. Define and test the exact sent-state evidence before enabling cleanup: only `VacancyStatus.applied` currently indicates completed application submission, but its timestamp is absent. Require an explicit application/submission timestamp for 60-day cleanup enforcement; never delete source candidate data or submission history.


## Stage 5: Database and models — **partially complete**

**Goal:** One SQLite database at `data/app.db`, with explicit lifecycle state and repeatable fresh-schema bootstrap.

### Completed

- `data/app.db` is the only canonical database.
- `Vacancy` has nullable `submit_email` and `submit_url`, plus a DB-level non-blank contact `CHECK`; legacy `credentials` and `url` fields are removed.
- `submit_url` is unique when present; email-only vacancies are supported.
- Old empty `resources/app.db` is removed.
- Alembic configuration, revisions, and dependency are removed; SQLAlchemy `init_db()` creates a fresh schema.

### Remaining

1. Add history/retry/failure-reason fields only when scheduling or operator triage needs them.
2. Add outbox/delivery-attempt records before enabling automatic email, Telegram or application submission retries.
3. Audit one-to-one relationships and indexes separately; do not bundle schema redesign into JobSpy search work.

## Stage 6: Application Submission Automation — **not started / unverified**

**Goal:** Submit a reviewed and explicitly eligible vacancy through an external portal or LinkedIn Easy Apply.

1. Define safe input/output contract and permitted lifecycle transitions.
2. Require idempotency and an application-attempt record before invoking a portal.
3. Test with fake browser/portal responses; no real submission in unit tests.
4. Keep manual operator authorization policy separate from technical retries.

## Stage 7: OpenAI-compatible LLM configuration — **complete for configuration; connectivity pending**

**Goal:** Every CrewAI crew uses the same gateway configuration.

### Completed

- `LLM_BASE_URL` defaults to `http://id-vps:20128/v1`.
- `create_llm()` uses CrewAI `custom_openai=True`, `base_url`, model and API key.
- Query and vacancy-review crews use the common factory; resume/evaluation/email crews receive the same base URL.
- `.env.example` documents `LLM_BASE_URL` without a real key.

### Remaining

1. Set `LLM_MODEL` and secret `LLM_API_KEY` in the real ignored `.env` without printing them.
2. Run an opt-in non-secret gateway smoke test from the intended Podman network.
3. Standardize embedding provider separately; it is not automatically covered by `LLM_BASE_URL`.

## Stage 8: Podman Compose operations — **partially complete**

**Goal:** Repeatable Podman Compose lifecycle without embedding mutable data in images.

### Completed

- Compose declares `cloak-browser`, production-only commented `linkedin-bot`, `antigravity-cli`, and `sqlite-ui`.
- `linkedin-bot` default command remains the complete `main.py` pipeline but is not started during laptop development.
- Database and session state are runtime volumes, not copied into the application image.
- `sqlite-ui` mounts `data/` writable so its single-row and bulk delete UI work.
- `antigravity-cli` has a persistent named `/workspace` volume for documented agent artifacts and reusable workspace skills.

### Remaining

1. Add minimal root-level operator commands/documentation for `podman compose build`, `up`, logs and the sequential pipeline.
2. Verify image build under Podman; resolve Dockerfile portability defects only if observed.
3. Keep `sqlite-ui` off production networks or bind it only to a safe interface before using it outside local debugging.

## Definition of ready for the next agent

Before changing a stage, the agent must read this file, inspect `git status`, run the stage-specific focused tests, and preserve these invariants:

- one database: `data/app.db`;
- one session path: `data/state.json`;
- LinkedIn Post Vacancy Collector, JobSpy Vacancy Search, Vacancy Review and Resume Generation, and Application Harness remain ordered components;
- `main.py` is the only pipeline entry point; JobSpy is always Step 2;
- Podman Compose is the runtime; CDP is internal-only;
- no secrets, cookies, DB files, generated resumes or caches are committed.
