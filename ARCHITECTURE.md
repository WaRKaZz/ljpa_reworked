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

- `python -m ljpa_reworked.main`: intentional full pipeline: collection, evaluation, materials and delivery/application paths.
- `python -m ljpa_reworked.main --discovery`: JobSpy discovery only. It does not review vacancies, create resumes, send messages or apply.

## Pipeline components

1. **LinkedIn Post Vacancy Collector:** Antigravity/Playwright component that collects LinkedIn post vacancies.
2. **JobSpy Vacancy Discovery:** database-only JobSpy discovery component.
3. **Application Submission Automation:** planned component for submitting an explicitly eligible vacancy; it is not yet verified.

## LLM configuration

CrewAI uses an OpenAI-compatible gateway configured by `LLM_BASE_URL`, defaulting to `http://id-vps:20128/v1`. The API key remains in the ignored `.env`; it is never committed or printed.

## Lifecycle safeguards

`Vacancy.status` is explicit and non-null. JobSpy identifies vacancies by non-empty URL and refreshes source-owned fields without changing workflow status. External delivery/submission needs idempotency and delivery-attempt records before automated retries are enabled.
