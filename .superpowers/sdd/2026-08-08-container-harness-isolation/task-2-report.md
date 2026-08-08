# Task 2 Report: Refactor Host Wrappers for Podman Exec Delegation

## Summary
Successfully refactored host service wrappers in `src/ljpa_reworked/services/harness/posts_scraper.py` and backward-compatibility shims (`src/ljpa_reworked/services/harness_posts_scraper.py`, `src/ljpa_reworked/services/harness_jobspy.py`) to delegate execution to container workers (`/app/linkedin_posts_agent.py` and `/app/jobspy_etl_fetcher.py`).

## Implementation Details
1. **Host Wrapper (`src/ljpa_reworked/services/harness/posts_scraper.py`)**:
   - Implemented `run_linkedin_posts_agent(prompt: str | None = None, verbose: bool = False) -> str` which delegates execution to `podman exec -i antigravity-cli-dev python /app/linkedin_posts_agent.py`.
   - Aliased `run_agy_harness_sdk` to `run_linkedin_posts_agent` for backward compatibility.
2. **Backward-Compatibility Shims**:
   - Updated `src/ljpa_reworked/services/harness_posts_scraper.py` to export `run_linkedin_posts_agent`.
3. **Tests (`tests/test_harness_posts_scraper.py`)**:
   - Added `test_run_linkedin_posts_agent_delegates_to_container` asserting proper command args (`podman exec -i antigravity-cli-dev python /app/linkedin_posts_agent.py`).
   - Updated `test_run_agy_harness_sdk_executes_podman_exec` to test the alias target `/app/linkedin_posts_agent.py`.

## Verification Evidence
Executed pytest suite:
- `uv run pytest tests/test_harness_posts_scraper.py tests/test_harness_jobspy.py` (Passed 6/6 tests)
- `uv run pytest tests/` (Passed 20/20 tests)
