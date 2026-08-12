# Architecture Overview

## Runtime topology

The project runs with Podman Compose. Mutable state is host-mounted and never baked into application images.

```text
Podman network: ljpa-network

cloak-browser
  └─ internal CDP: http://cloak-browser:9222

linkedin-bot
  ├─ runs: python -m ljpa_reworked.main
  ├─ owns the application pipeline and SQLite operations
  ├─ reads/writes: /app/data/app.db
  └─ requests agent work from antigravity-cli

antigravity-cli
  ├─ runs agy/MCP agent tasks only
  ├─ runs LinkedIn Post Vacancy Collector
  └─ serves internal API at http://antigravity-cli:8080/run-harness

sqlite-ui (optional debug profile)
  └─ read-only view of /data/app.db
```

## Development workflow

Development TODOs under `docs/plans/` run directly on `id-laptop` with `agy --print --dangerously-skip-permissions`. This is separate from the runtime path: `linkedin-bot` Python calls the `antigravity-cli` container API through `harness_runner.py`.

## Persistent paths

- `data/app.db`: only canonical SQLite database.
- `data/state.json`: LinkedIn Playwright storage state; secret, ignored by Git.
- `resources/`: candidate profile and static source material; mounted read-only in runtime containers.

## Execution modes

- `python -m ljpa_reworked.main`: one intentional sequential pipeline: LinkedIn-post harness collection, JobSpy search, vacancy review, resume generation, then application harness.
- There is no standalone `--discovery` mode. JobSpy search is always Step 2 of this sequence.

## Pipeline components

1. **LinkedIn Post Vacancy Collector:** Antigravity/Playwright component that collects LinkedIn post vacancies.
2. **JobSpy Vacancy Search:** searches JobSpy and saves or refreshes vacancies by URL before review.
3. **Vacancy Review and Resume Generation:** reviews saved vacancies and creates a tailored resume for each eligible vacancy.
4. **Application Submission:** email path is implemented, Telegram notifications are disabled, and application harness is not yet verified.

## LLM configuration

CrewAI uses an OpenAI-compatible gateway configured by `LLM_BASE_URL`, defaulting to `http://id-vps:20128/v1`. The API key remains in the ignored `.env`; it is never committed or printed.

## Lifecycle safeguards

`Vacancy.status` is explicit and non-null. JobSpy identifies vacancies by non-empty URL and refreshes source-owned fields without changing workflow status. External delivery/submission needs idempotency and delivery-attempt records before automated retries are enabled.
