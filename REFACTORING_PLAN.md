# Global Project Refactoring Plan

> **Runtime decision:** Podman Compose. `linkedin-bot` is the application container; its Python calls the isolated `antigravity-cli` runtime API for agent tasks. Development TODOs are implemented separately with direct host `agy` on `id-laptop`. `main.py` intentionally runs the complete pipeline. Use `python -m ljpa_reworked.main --discovery` only for the isolated JobSpy discovery mode.

## Current baseline — verified 2026-08-10

- Canonical SQLite database: `data/app.db`; 39 vacancies; Alembic revision `f6c1f6797747`.
- `resources/app.db` was an empty obsolete artifact and was removed.
- The canonical DB passed `PRAGMA integrity_check` after migration.
- LinkedIn login/session bootstrap is implemented and operational; `data/state.json` remains its canonical ignored state path.
- LLM gateway: OpenAI-compatible `http://id-vps:20128/v1`, configured by `LLM_BASE_URL`.
- Quality baseline: `uv run pytest -q`, `uv run --extra dev ruff check src tests`, `uv run python -m compileall -q src`, and `podman compose config -q`.
- The project has exactly two harnesses: Harness 1 collects LinkedIn posts; Harness 2 applies to vacancies. There is no Harness 3.

## Stage 1: Agent-based job collection — **partially complete**

**Goal:** Keep agent work in `antigravity-cli`, not inside the application container.

### Completed

- `antigravity-cli` is a distinct runtime service with `agy`, MCP tools and `harness_server.py`.
- Development TODOs are executed separately with direct host `agy`, not through this runtime service.
- `linkedin-bot` remains the production application container.
- Harness runner sends requests to `http://antigravity-cli:8080/run-harness` over the internal network.
- `main.py` calls the full pipeline by design.

### Remaining

1. Define the safe Harness 1 prompt contract and add a hermetic text-level contract test. The prompt must use `data/state.json`, `Vacancy.status='created'`, and `LinkedinPost.processed=False`; it must stop safely on login, CAPTCHA, or access blockers and never bypass access controls.
2. Implement normalized, transactional `LinkedinPost`/`Vacancy` persistence through project operations and test it with a disposable SQLite database.
3. Add a hermetic fake-runner test for Harness 1 request/response handling. Do not contact LinkedIn in unit tests.
4. Replace stale paths and names in harness prompts and docs; then decide whether host port `8080` is needed and remove it if calls originate only from `linkedin-bot`.

## Stage 2: JobSpy discovery and ETL — **complete for unit scope; live smoke test pending**

**Goal:** Discover JobSpy vacancies only; never review, generate materials, send messages, or apply.

### Completed

- `JobSpyIntegrationService` generates profile-grounded CrewAI queries with a SHA-256 cache.
- Query contract validates source, bounds, hash and normalized duplicate queries.
- A mismatched LLM profile hash fails without overwriting a valid cache.
- URL is the canonical JobSpy identity; blank URLs are skipped and existing source fields refresh without changing lifecycle state.
- `VacancyStatus` replaced `Vacancy.processed`; migration backfilled existing data and `Vacancy.url` has a uniqueness constraint.
- `python -m ljpa_reworked.main --discovery` is isolated and returns summary metrics.

### Remaining

1. Execute one controlled network-enabled `--discovery` run only after verifying credentials/provider settings; inspect its summary and DB writes.
2. Remove legacy hard-coded JobSpy calls from the full `main.py` pipeline after Harness 2 is explicitly switched to `JobSpyIntegrationService`.
3. Do not create a fallback identity for URL-less rows unless JobSpy supplies a proven immutable source ID.

## Stage 3: QA gates — **partially complete**

**Goal:** Reliable gates, not an arbitrary 100% coverage target.

### Completed

- Unit and acceptance tests exist for statuses, migrations, query validation/cache, URL upsert, discovery isolation, Compose structure, session paths and LLM gateway construction.
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
3. Audit one-to-one relationships and indexes separately; do not bundle schema redesign into discovery work.

## Stage 6: Vacancy application automation (Harness 2) — **not started / unverified**

**Goal:** Harness 2 applies to a reviewed and explicitly eligible vacancy through an external portal or LinkedIn Easy Apply.

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

1. Add minimal root-level operator commands/documentation for `podman compose build`, `up`, logs and discovery-only execution.
2. Verify image build under Podman; resolve Dockerfile portability defects only if observed.
3. Keep `sqlite-ui` off production networks or bind it only to a safe interface before using it outside local debugging.

## Definition of ready for the next agent

Before changing a stage, the agent must read this file, inspect `git status`, run the stage-specific focused tests, and preserve these invariants:

- one database: `data/app.db`;
- one session path: `data/state.json`;
- two harnesses only;
- `main.py` is the complete pipeline; `--discovery` is isolated;
- Podman Compose is the runtime; CDP is internal-only;
- no secrets, cookies, DB files, generated resumes or caches are committed.
