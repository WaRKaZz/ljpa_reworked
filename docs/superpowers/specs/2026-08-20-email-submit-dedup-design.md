# Email Submit 30-Day Recipient Deduplication Design

## Overview
When running `--email-submit` (`submit_top_email_vacancies`), LJPA should check if an application email has already been sent to the target recipient (`submit_email` / `recipient`) within the past 30 days (rolling window). If a prior application to this recipient was sent within the last 30 days, the candidate should not apply again; instead, the vacancy is archived (`VacancyStatus.archived`) and skipped.

## Requirements
1. **Recipient Match**: Match against `Email.recipient` where `Email.sent == True`.
2. **Timeframe**: 30-day rolling window (`Email.created_at >= now - timedelta(days=30)`).
3. **Action on Match**:
   - Log informative message about skipping duplicate recipient.
   - Transition vacancy status to `VacancyStatus.archived`.
   - Skip AI resume/cover letter generation and email dispatch.
4. **Operations Export**: Provide `has_recent_sent_email_to_recipient` in `ljpa_reworked.operations` / `email_ops.py`.
5. **Testing**: Comprehensive unit and workflow tests covering:
   - Recent email sent (<30 days) -> True.
   - Old email sent (>30 days) -> False.
   - Unsent email (`sent=False`) -> False.
   - Vacancy auto-archival and non-resubmission in `submit_top_email_vacancies`.
   - Batch handling with multiple identical recipients in queue.

## Proposed Changes

### `src/ljpa_reworked/operations/email_ops.py`
Add `has_recent_sent_email_to_recipient(db: Session, recipient: str, days: int = 30, *, now: datetime | None = None) -> bool`.

### `src/ljpa_reworked/operations/__init__.py`
Export `has_recent_sent_email_to_recipient`.

### `src/ljpa_reworked/main.py`
In `submit_top_email_vacancies`:
After resolving `recipient`:
Check `has_recent_sent_email_to_recipient(db, recipient=recipient, days=30)`.
If True, call `transition_vacancy_status(db, vacancy.id, VacancyStatus.archived)` and continue.

### `tests/test_email_submission_workflow.py`
Add unit tests for `has_recent_sent_email_to_recipient` and integration tests for `submit_top_email_vacancies` verifying archival and skip behavior.
