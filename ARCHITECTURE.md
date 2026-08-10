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
  ├─ executes Harness 1 (LinkedIn posts collection)
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

## Harnesses

1. **Harness 1:** Antigravity/Playwright LinkedIn posts collector.
2. **Harness 2:** Vacancy application automation. It is planned, not yet verified.

## LLM configuration

CrewAI uses an OpenAI-compatible gateway configured by `LLM_BASE_URL`, defaulting to `http://id-vps:20128/v1`. The API key remains in the ignored `.env`; it is never committed or printed.

## Lifecycle safeguards

`Vacancy.status` is explicit and non-null. JobSpy identifies vacancies by non-empty URL and refreshes source-owned fields without changing workflow status. External delivery/submission needs idempotency and delivery-attempt records before automated retries are enabled.
