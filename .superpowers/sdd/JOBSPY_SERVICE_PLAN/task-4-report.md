# Task 4 Implementation Report: Profile-Hash Cache with Atomic Persistence

## Implementation Overview

Task 4 of the `JOBSPY_SERVICE_PLAN` has been successfully implemented in `src/ljpa_reworked/services/jobspy.py` with comprehensive unit tests in `tests/test_task4_jobspy_cache.py`.

### Key Enhancements Implemented in `src/ljpa_reworked/services/jobspy.py`:

1. **Dynamic Resource Path Resolution**:
   - `PROJECT_ROOT` is dynamically computed relative to `Path(__file__).resolve().parents[3]` (`src/ljpa_reworked/services/jobspy.py` -> project root).
   - Default paths are set to `PROJECT_ROOT / "resources" / "profile.md"` and `PROJECT_ROOT / "resources" / "profile_search_query.json"`, avoiding dependency on `os.getcwd()`.

2. **SHA-256 Profile Hashing**:
   - `compute_profile_sha256(profile_path: Path)` reads profile text from exact UTF-8 bytes and calculates SHA-256 digest (`hexdigest()`).

3. **Validated Cache Loading**:
   - `load_cached_queries(cache_path: Path, expected_sha256: str)` uses `JobSearchQuerySet.model_validate_json(content)` to load and validate cached JSON.
   - Cache is invalidated and returns `None` if the file does not exist, JSON is corrupted/malformed, schema validation fails, or stored `profile_sha256` does not match `expected_sha256`.

4. **Atomic Cache Persistence**:
   - `atomic_write_cache(cache_path: Path, query_set: JobSearchQuerySet)` writes `query_set.model_dump_json(indent=2)` to a temporary sibling file (`f"{cache_path.name}.tmp.{uuid.hex}"`).
   - Flushes stream (`f.flush()`) and forces disk sync (`os.fsync(f.fileno())`) before replacing target path atomically via `temp_path.replace(cache_path)`.

5. **CrewAI Query Generation & Fallback Protection**:
   - `generate_and_cache_queries(...)` triggers `QueryGenerationCrew` (or configurable/mockable `crew_runner`).
   - On CrewAI failure, logs error and raises contextual `RuntimeError(f"CrewAI query generation failed: {e}")`.
   - Leaves existing cache file on disk untouched in case of failure.

6. **Query Normalization & Deduplication**:
   - `normalize_and_deduplicate_queries(queries: list[JobSearchQuery])` deduplicates search queries using normalized key `(q.site_name, q.search_term.lower().strip(), q.location.lower().strip())`.

7. **Service Class**:
   - `JobSpyIntegrationService`: Exposes `get_queries()` which returns validated, cached/generated, deduplicated search queries.

---

## Unit Testing & Verification

Unit tests were written in `tests/test_task4_jobspy_cache.py` following strict TDD principles:

1. **Unchanged Profile Reuse**:
   - `test_unchanged_profile_reuses_valid_cache` verifies that matching profile SHA256 reuses disk cache without invoking CrewAI.
2. **Profile Change & Cache Update**:
   - `test_changed_profile_retriggers_crewai_generation_and_updates_cache` verifies profile modifications trigger CrewAI query generation with new SHA256 and update cache file on disk.
3. **Corrupt Cache Handling**:
   - `test_corrupt_cache_file_forces_regeneration` verifies malformed JSON forces regeneration and rewrites valid cache file.
4. **CrewAI Failure & Cache Preservation**:
   - `test_crewai_failure_raises_exception_and_preserves_previous_valid_cache_file` verifies LLM/CrewAI errors raise `RuntimeError` and preserve existing cache file.
5. **Deduplication Verification**:
   - `test_duplicate_queries_deduplication` verifies whitespace and case-insensitive deduplication across query lists.
6. **Service Integration**:
   - `test_jobspy_integration_service_queries` verifies `JobSpyIntegrationService.get_queries()` returns deduplicated queries.

### Test Execution Results:
```
tests/test_jobspy_service.py .                                           [  6%]
tests/test_task4_jobspy_cache.py .......                                 [ 50%]
tests/test_task3_query_generation_crew.py ........                       [100%]

============================== 16 passed in 4.73s ==============================
```

---

## Git Commit Summary

- Files modified:
  - `src/ljpa_reworked/services/jobspy.py`
- Files created:
  - `tests/test_task4_jobspy_cache.py`
  - `.superpowers/sdd/JOBSPY_SERVICE_PLAN/task-4-report.md`
