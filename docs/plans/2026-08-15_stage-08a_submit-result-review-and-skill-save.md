# Stage 08a — Review submit result before changing vacancy status

**Plan reference:** `ARCHITECTURE.md`, application-submission path. The current tree has no `REFACTORING_PLAN.md`.

**Objective:** Mark a URL application submitted only after a bounded CrewAI review of its AGY stream decides ATS submission succeeded. On failure mark `application_error` and notify the configured LJPA Telegram chat. On success invoke a separate, non-blocking skill-save AGY pass for the original conversation.

## Agreed behavior

1. First submit uses the existing `prompts/harness_submit.md`.
2. Parse the streamed JSONL in `harness_submit()` into a Python-local result object. Extract `conversation_id` directly from events and retain only the last 40 ordered lines for review.
3. CrewAI receives only that 40-line tail as untrusted evidence and returns exactly `success|error` with `error_description`. It does **not** return a conversation ID.
4. Review `error`: transition the vacancy to `application_error`; send one concise redacted notification through existing `Telegram().send_message()` configured from `BOT_TOKEN`/`CHAT_ID`.
5. Review `success`: transition immediately to `submitted_via_url`.
6. After success status is committed, launch a second AGY request with the original `conversation_id` and a dedicated English `prompts/harness_save_site_skill.md`.
7. The second prompt only saves a technical reusable site skill and allowed runtime metadata. It does not decide submission, write vacancy status, request review, or send Telegram.
8. Wrap second-pass execution in an explicit finite timeout and `try/except`. Timeout or exception sends one concise Telegram notification that skill saving failed. Keep `submitted_via_url`; never retry the application.
9. Do not add DB fields/tables/migrations or durable audit logs for stream, review, conversation ID, or skill saving.

## Scope

### In scope
- Typed/local first-pass result with `conversation_id` and a 40-line JSONL tail.
- Existing-CrewAI-compatible structured review adapter.
- Review-driven state changes and configured Telegram error notifications.
- Second AGY skill-save request, bound to original conversation ID.
- Split first/second prompts: first retains workspace and artifact basics; second exclusively authorizes sanitized skill saving.
- Hermetic tests and a local no-network dry-run.

### Out of scope
- Live ATS, LinkedIn, JobSpy, Gmail/IMAP, Telegram, or application effects.
- DB schema changes, candidate/profile/resume changes, `.env`, `data/state.json`, `resources/`, workspace content, browser state, or automatic resubmission.

## Safety boundary

- **Allowed external effects:** None. Use fake HTTP/AGY/CrewAI/Telegram and disposable DB fixtures.
- **Forbidden effects:** Network, Podman build/restart, canonical `data/app.db` mutation, live application/email/Telegram.
- **Secrets:** Never read or print `.env`, profile, state, mailbox, cookies, OTPs, credentials, raw form values, or raw stream evidence.
- **Rollback:** `git restore` only listed source/prompt/test files.

## Preserve

- `data/app.db` is canonical; `submitted_via_url` is terminal; `application_error` is retryable.
- `/run-harness` provides NDJSON and serializes AGY with `harness_lock`.
- `runtime/` is persistent but Git-ignored.
- Existing first-pass prompt keeps read-only IMAP and base workspace artifact rules.
- Skills/README must contain technical reusable facts only; policy-permitted runtime identity/auth metadata belongs only in `/runtime/workspace/credentials.json`.

## Files

- Modify: `src/ljpa_reworked/services/harness_runner.py` — result model, tail parser, conversation extraction, bounded second pass at the smallest existing seam.
- Modify: `src/ljpa_reworked/main.py` — review decision, state transitions, Telegram notifications, post-success sequencing.
- Modify only if needed: `src/ljpa_reworked/services/harness/harness_server.py` — safe existing-conversation request support; preserve lock/NDJSON.
- Modify: `prompts/harness_submit.md` — retain base workspace privacy/artifact rules, remove final skill-authoring task.
- Create: `prompts/harness_save_site_skill.md` — English-only, technical-only skill/README instructions, personal-data cleanup, permitted metadata only in `credentials.json`.
- Modify/Create focused tests: `tests/test_harness_runner.py`, `tests/test_url_submission_harness.py`, `tests/test_main_modes.py`, `tests/test_submission_result_review.py`.
- Do not touch: `.env`, `data/app.db`, `data/state.json`, `resources/`, `runtime/`, unrelated worktree changes.

## TDD steps

1. Read current `HarnessRequest`, stream event formats, `parse_terminal_result`, submit orchestration, `Telegram`, and existing CrewAI structured-output usage. Confirm every API signature before calling it.
2. Add a failing parser test: representative JSONL extracts `conversation_id`; preserves order; tail is exactly 40 lines or all available lines. Implement smallest typed result and keep CLI exit compatibility.
3. Add failing review-adapter tests: it receives only the 40-line tail; accepted return shape is decision plus description; malformed output becomes `error`. Implement minimum existing-CrewAI-compatible adapter.
4. Add failing orchestration tests:
   - review error writes disposable vacancy `application_error` and calls mocked Telegram once with redacted text;
   - review success writes `submitted_via_url` before second AGY starts;
   - second pass receives first-pass conversation ID, not a CrewAI field;
   - timeout/exception preserves `submitted_via_url`, never repeats submit, and calls mocked Telegram once.
5. Implement the smallest orchestration. Keep the second-pass `try/except` narrow and timeout explicit.
6. Split prompts and add contract tests: first prompt keeps base workspace rules but has no final skill authoring; second prompt requires technical-only skill/README and forbids personal data, credentials, OTPs, raw transcript retention.
7. Execute hermetic tests, ruff, compileall, then local dry-run with every external boundary mocked. Prove no real socket, Telegram transport, ATS, or canonical DB write.

## Acceptance criteria

- [ ] First-pass result retains only local conversation ID and last 40 JSONL lines.
- [ ] CrewAI returns only decision and error description from that tail.
- [ ] Error produces `application_error` plus exactly one redacted configured-LJPA Telegram notification.
- [ ] Success commits `submitted_via_url` before skill saving starts.
- [ ] Second AGY gets original `conversation_id`, uses only dedicated English prompt, and cannot affect application state.
- [ ] Second-pass timeout/exception sends one notification and preserves `submitted_via_url`; no retry occurs.
- [ ] No DB schema/persistent audit change exists.
- [ ] Prompts obey technical-skill vs runtime-metadata privacy boundaries.
- [ ] Tests and dry-run prove zero live effects.

## Required verification

```bash
uv run pytest --no-cov -q tests/test_harness_runner.py tests/test_url_submission_harness.py tests/test_main_modes.py tests/test_submission_result_review.py
uv run ruff check src/ljpa_reworked/services/harness_runner.py src/ljpa_reworked/main.py src/ljpa_reworked/services/harness/harness_server.py tests/
uv run python -m compileall -q src
uv run pytest -q tests/test_harness_runner.py tests/test_url_submission_harness.py tests/test_main_modes.py tests/test_submission_result_review.py
```

State focused test results separately if repository-wide coverage affects targeted runs. Do not claim a full suite without running it.

## agy execution contract

Run on `id-laptop` from the repository root. Read this TODO, `ARCHITECTURE.md`, named source files, and tests before edits.

- Follow TDD and this safety boundary exactly.
- Preserve unrelated existing worktree changes.
- Do not run or contact live services.
- Do not expose candidate or secret data.
- Stop and report API uncertainty; do not guess.
- Do not delete this TODO or commit. Hermes verifies completion independently.

## Final report

Report changed files, red/green test evidence, actual commands and outcomes, proof of no live effects, dry-run result, deviations, and the exact recommended next TODO.
