# Email Submit 30-Day Recipient Deduplication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent resending email applications to the same recipient within 30 days during `--email-submit`, auto-archiving the duplicate vacancy.

**Architecture:** Add `has_recent_sent_email_to_recipient` in `email_ops.py` to query `Email.sent == True` and `Email.created_at >= now - 30d`. In `main.py:submit_top_email_vacancies`, invoke this check before generating emails/resumes; if true, archive vacancy and skip.

**Tech Stack:** Python 3.12, SQLAlchemy, pytest, uv.

## Global Constraints
- Timeframe is a rolling 30-day window (`created_at >= now - timedelta(days=30)`).
- Match target is `Email.recipient` where `Email.sent` is `True`.
- Vacancies with recent duplicate recipients must transition to `VacancyStatus.archived`.

---

### Task 1: Add `has_recent_sent_email_to_recipient` in `email_ops.py` and export in `operations`

**Files:**
- Modify: `src/ljpa_reworked/operations/email_ops.py`
- Modify: `src/ljpa_reworked/operations/__init__.py`
- Test: `tests/test_email_submission_workflow.py`

**Interfaces:**
- Produces: `has_recent_sent_email_to_recipient(db: Session, recipient: str, days: int = 30, *, now: datetime | None = None) -> bool`

- [ ] **Step 1: Write the failing tests in `tests/test_email_submission_workflow.py`**

```python
def test_has_recent_sent_email_to_recipient():
    db, engine = _session()
    try:
        now = datetime(2026, 8, 20, 12, 0, 0)
        v = create_vacancy_direct(db, title="Test Job", text="Text", submit_email="hr@test.com")
        
        # Unsent email
        e1 = Email(
            vacancy_id=v.id,
            subject="Subj 1",
            recipient="hr@test.com",
            sent=False,
            created_at=now - timedelta(days=5),
        )
        db.add(e1)
        db.commit()
        assert not has_recent_sent_email_to_recipient(db, "hr@test.com", days=30, now=now)

        # Sent email > 30 days ago
        e2 = Email(
            vacancy_id=v.id,
            subject="Subj 2",
            recipient="hr@old.com",
            sent=True,
            created_at=now - timedelta(days=31),
        )
        db.add(e2)
        db.commit()
        assert not has_recent_sent_email_to_recipient(db, "hr@old.com", days=30, now=now)

        # Sent email <= 30 days ago
        e3 = Email(
            vacancy_id=v.id,
            subject="Subj 3",
            recipient="hr@recent.com",
            sent=True,
            created_at=now - timedelta(days=10),
        )
        db.add(e3)
        db.commit()
        assert has_recent_sent_email_to_recipient(db, "hr@recent.com", days=30, now=now)
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_email_submission_workflow.py::test_has_recent_sent_email_to_recipient -v`

- [ ] **Step 3: Implement `has_recent_sent_email_to_recipient` in `email_ops.py` and export in `__init__.py`**

In `src/ljpa_reworked/operations/email_ops.py`:
```python
def has_recent_sent_email_to_recipient(
    db: Session,
    recipient: str,
    days: int = 30,
    *,
    now: datetime | None = None,
) -> bool:
    """Check if an email was sent to this recipient within the last `days` days."""
    if not recipient or not str(recipient).strip():
        return False
    now = now or datetime.now(UTC).replace(tzinfo=None)
    cutoff = now - timedelta(days=days)
    count = (
        db.query(Email)
        .filter(
            Email.recipient == recipient.strip(),
            Email.sent.is_(True),
            Email.created_at >= cutoff,
        )
        .count()
    )
    return count > 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_email_submission_workflow.py::test_has_recent_sent_email_to_recipient -v`

- [ ] **Step 5: Commit Task 1**

```bash
git add src/ljpa_reworked/operations/email_ops.py src/ljpa_reworked/operations/__init__.py tests/test_email_submission_workflow.py
git commit -m "feat(email_ops): add has_recent_sent_email_to_recipient check"
```

---

### Task 2: Integrate 30-day check and auto-archival in `submit_top_email_vacancies`

**Files:**
- Modify: `src/ljpa_reworked/main.py:162-260`
- Test: `tests/test_email_submission_workflow.py`

**Interfaces:**
- Consumes: `has_recent_sent_email_to_recipient`, `transition_vacancy_status`, `VacancyStatus.archived`

- [ ] **Step 1: Write integration tests for `submit_top_email_vacancies` 30-day duplicate handling**

In `tests/test_email_submission_workflow.py`:
- Test skipping/archiving a vacancy whose recipient already received a sent email within 30 days.
- Test queue batch deduplication where 2 vacancies in the same queue share the same recipient.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_email_submission_workflow.py::test_submit_top_email_vacancies_skips_and_archives_recent_recipient -v`

- [ ] **Step 3: Update `submit_top_email_vacancies` in `src/ljpa_reworked/main.py`**

Import `has_recent_sent_email_to_recipient` from `ljpa_reworked.operations`.
In `submit_top_email_vacancies`, after `recipient = extract_primary_email(vacancy.submit_email) or vacancy.submit_email`:
```python
        if has_recent_sent_email_to_recipient(db, recipient=recipient, days=30):
            logger.info(
                "Skipping vacancy %s: email already sent to %s within the last 30 days. Archiving vacancy.",
                vacancy.id,
                recipient,
            )
            transition_vacancy_status(db, vacancy.id, VacancyStatus.archived)
            continue
```

- [ ] **Step 4: Run all tests to verify they pass**

Run: `uv run pytest tests/test_email_submission_workflow.py -v`
Run: `uv run ruff check .`
Run: `uv run ruff format --check .`

- [ ] **Step 5: Commit Task 2**

```bash
git add src/ljpa_reworked/main.py tests/test_email_submission_workflow.py
git commit -m "feat(main): skip and archive email vacancies with responses in last 30 days"
```
