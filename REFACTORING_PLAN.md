# Global Project Refactoring Plan

> **Runtime decision:** Podman Compose. `linkedin-bot` is the application container; its Python calls the isolated `antigravity-cli` runtime API for agent tasks. Development TODOs are implemented separately with direct host `agy` on `id-laptop`. `main.py` intentionally runs the complete pipeline. The pipeline has no standalone JobSpy mode: it runs sequentially after LinkedIn-post collection and before review.

## Current baseline — verified 2026-08-10

- Canonical SQLite database: `data/app.db`; 39 vacancies; Alembic revision `f6c1f6797747`.
- `resources/app.db` was an empty obsolete artifact and was removed.
- The canonical DB passed `PRAGMA integrity_check` after migration.
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

- The LinkedIn Post Vacancy Collector is implemented, working, and tested by the operator.
- It reads candidate material, uses the canonical ignored `data/state.json` session state, collects LinkedIn post vacancies, and persists normalized `LinkedinPost`/`Vacancy` records.

### Follow-up maintenance

- Keep its prompt, schema terminology, and tests aligned when the collector changes. This is maintenance, not an open implementation stage.

## Stage 1A: Direct LinkedIn vacancies and fresh database baseline — **complete / verified by operator**

**Goal:** Harness 1 validates LinkedIn posts itself and writes final vacancies directly to `data/app.db`; no raw-post table or post-review crew remains.

## Stage 1B: Vacancy submission contact model and fresh database — **complete / verified by operator**

**Goal:** Replace legacy `Vacancy.credentials` and `Vacancy.url` with explicit nullable `submit_email` and `submit_url`, enforce database-level contact check constraint, and replace Alembic with explicit SQLAlchemy metadata bootstrap (`init_db()`).

### Completed

- Removed legacy fields `credentials` and `url` from `Vacancy` model and Pydantic schemas.
- Added explicit nullable `submit_email` and `submit_url` with SQLite database-level `CHECK` constraint `(submit_email IS NOT NULL AND TRIM(submit_email) != '') OR (submit_url IS NOT NULL AND TRIM(submit_url) != '')`.
- Pydantic models normalize blank strings to `None`, validate email syntax, and enforce at least one contact method.
- Updated Harness prompt, JobSpy mapping, Crew task templates, operations, and main workflow to use `submit_email` and `submit_url`.
- Removed Alembic configuration and dependency; added explicit SQLAlchemy metadata bootstrap `init_db()`.
- Backed up canonical database, recreated fresh `data/app.db` via `init_db()`, and verified with `PRAGMA integrity_check`.


## Stage 2: JobSpy search and ETL — **complete for unit scope; sequential integration pending**

**Goal:** Search JobSpy and save or refresh vacancies as Step 2, after LinkedIn harness collection and before review.

### Completed

- `JobSpyIntegrationService` generates profile-grounded CrewAI queries with a SHA-256 cache.
- Query contract validates source, bounds, hash and normalized duplicate queries.
- A mismatched LLM profile hash fails without overwriting a valid cache.
- URL is the canonical JobSpy identity; blank URLs are skipped and existing source fields refresh without changing lifecycle state.
- `VacancyStatus` replaced `Vacancy.processed`; migration backfilled existing data and `Vacancy.url` has a uniqueness constraint.
- `JobSpyIntegrationService.run()` returns summary metrics for the Step-2 search.

### Remaining

1. Replace legacy hard-coded JobSpy calls in `main.py` with `JobSpyIntegrationService.run()` so JobSpy is the second sequential step.
2. Verify the sequential hand-off with fakes: harness collection, JobSpy search, then review; do not make a live network run part of this stage.
3. Do not create a fallback identity for URL-less rows unless JobSpy supplies a proven immutable source ID.

## Stage 3: QA gates — **partially complete**

**Goal:** Reliable gates, not an arbitrary 100% coverage target.

### Completed

- Unit and acceptance tests exist for statuses, migrations, query validation/cache, URL upsert, sequential JobSpy integration, Compose structure, session paths and LLM gateway construction.
- Ruff and Python compilation pass.
- Migration was verified on a disposable copy before applying to canonical `data/app.db`.

### Remaining

1. Add a coverage threshold only after measuring meaningful baseline coverage; do not require 100% by decree.
2. Run `podman compose config -q` after every Compose edit.
3. Build images and run isolated tests with `--network none`; do not start the full external-effect pipeline as a generic smoke test.
4. Add a live, opt-in smoke-test script for the LLM gateway and JobSpy. It must not print secrets or profile contents.

## Stage 4: Resume generation with RenderCV — **not started / unverified**

**Goal:** Replace legacy resume generation with RenderCV-produced ATS PDF output.

1. Inventory current generator inputs and output paths.
2. Add a minimal RenderCV render fixture and test before changing the workflow.
3. Keep generated resumes out of Git and store per-vacancy output metadata in the canonical DB.
4. Update `ResumeGenerationCrew` only after the renderer path is verified.

## Stage 5: Database and models — **partially complete**

**Goal:** One SQLite database at `data/app.db`, with explicit lifecycle state and repeatable migrations.

### Completed

- `data/app.db` is the only canonical database.
- Status migration and URL uniqueness migration are applied at `f6c1f6797747`.
- Old empty `resources/app.db` is removed.
- Alembic configuration points to `data/app.db`.

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

- Compose declares `cloak-browser`, `linkedin-bot`, `antigravity-cli`, and optional `sqlite-ui` debug profile.
- `linkedin-bot` default command runs the complete `main.py` pipeline.
- Database and session state are runtime volumes, not copied into the application image.
- `sqlite-ui` is read-only and enabled only via the `debug` profile.

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
