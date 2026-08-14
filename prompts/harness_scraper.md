# LINKEDIN DIRECT VACANCY DISCOVERY, VALIDATION, PERSISTENCE & SELF-AUDIT (REFACTORED V2)

## OBJECTIVE

Discover, validate, deduplicate, and persist up to 10 fresh, high-quality LinkedIn vacancies matching the candidate profile into a disposable workspace copy of the canonical database (`/runtime/workspace/app.db.work`). Replace the canonical database (`/runtime/harness-scraper/app.db`) atomically only after all post-insertion audits succeed.

Search LinkedIn posts only. Do not analyze the home feed, use direct messages, or apply to jobs.

---

## 1. BROWSER SETUP & STREAMLINED CDP WORKFLOW

Use MCP Unbrowse connected through Playwright/CDP at `http://cloak-browser:9222` for all browser actions.

### Connection Protocol
1. **Direct CDP Connection**: Connect Playwright over CDP: `browser = playwright.chromium.connect_over_cdp('http://cloak-browser:9222')`.
2. **Context & Active Page**: Access existing context and active page: `context = browser.contexts[0]`, `page = context.pages[-1]`. Bring active page to front (`page.bring_to_front()`).
3. **Local CDP Fallback**: If local CDP on `127.0.0.1:9222` is closed and required by background utilities, run a local TCP proxy forwarding `127.0.0.1:9222` -> `cloak-browser:9222` and run `yes | unbrowse setup`.

---

## 2. DATABASE WORKSPACE & ATOMIC PUBLISHING

The canonical database is `/runtime/harness-scraper/app.db`. Never write to it directly during scraping, review, or audit.

1. **Workspace Copy Setup**: Copy `/runtime/harness-scraper/app.db` to `/runtime/workspace/app.db.work`. Run `PRAGMA integrity_check` on both files; proceed only if both return `ok`.
2. **Workspace Isolation**: Execute all reads, inserts, updates, deduplication checks, and audits exclusively against `/runtime/workspace/app.db.work`.
3. **Atomic Publication Protocol**:
   * Close all SQLite connections to `/runtime/workspace/app.db.work`.
   * Run `PRAGMA integrity_check` and `PRAGMA foreign_key_check` on `/runtime/workspace/app.db.work`.
   * Copy `/runtime/workspace/app.db.work` to temporary sibling file `/runtime/harness-scraper/app.db.next`.
   * Verify `PRAGMA integrity_check` on `app.db.next`.
   * Atomically publish using `os.replace('/runtime/harness-scraper/app.db.next', '/runtime/harness-scraper/app.db')`.
   * If any step fails, remove `/runtime/harness-scraper/app.db.next` and retain the original `/runtime/harness-scraper/app.db` unchanged.

---

## 3. PHASE 1 — DYNAMIC CANDIDATE PROFILE INGESTION

1. Inspect `resources/` and read candidate profile files (`resources/profile.md`).
2. Dynamically extract location, visa/work authorization constraints, acceptable work arrangements (remote/hybrid/onsite), technical skills, domain experience, role families, and seniority.
3. Build a concise internal candidate profile summary. Do not hardcode candidate names, locations, technologies, or titles.

---

## 4. PHASE 2 — DYNAMIC SEARCH STRATEGY

Generate up to 3 search passes dynamically from candidate profile:
* **PASS 1 — HIGH PRECISION**: Core role family + primary skills + vacancy intent terms (`hiring`, `vacancy`, `opening`, `apply`, `recruiter email`).
* **PASS 2 — ALTERNATIVE MATCHES**: Profile-derived role synonyms + domain terms + secondary skills.
* **PASS 3 — CONTROLLED BROADENING**: Broader queries while retaining key profile skills/domain constraints.

Each pass executes one LinkedIn post search query and up to 3 scroll-and-extraction cycles. Search LinkedIn posts only. Stop immediately once 10 fully validated vacancies pass final audit.

---

## 5. PHASE 3 — CANDIDATE EVALUATION & MANDATORY GATES

### Full Post Review Requirement
A search result card or snippet is metadata only. For every candidate vacancy:
1. Open the original LinkedIn post in the browser.
2. **Expand Post Body**: Always click "See more" to expand collapsed text before evaluating facts or extracting contact details.
3. **External Apply URL Unwrapping**: If the post contains an external application link or LinkedIn job page with an external "Apply" button, navigate/click to trigger redirects and extract the final vendor application URL as `submit_url`.

### Mandatory Evaluation Gates
Reject immediately if any gate fails:
* **GATE A — ACTUAL VACANCY**: Must be an active job post. Reject career advice, "open to work" posts, networking invitations, closed jobs, and staffing ads without specific roles.
* **GATE B — FRESHNESS**: Must be published within the last 30 days.
* **GATE C — APPLICATION CREDENTIALS**: Must provide at least one valid, non-DM contact method:
  * A syntactically valid recruiter/application email address (`submit_email`); OR
  * A verified external/ATS application URL (`submit_url`).
  * Reject if the only contact method is direct messaging ("DM me").
* **GATE D — LOCATION & ELIGIBILITY**: Reject if post states restrictions incompatible with candidate's location, visa status, or remote work constraints. Store `visa_status='NOT_SPECIFIED'`.
* **GATE E — SEMANTIC RELEVANCE**: Assign an internal match score (0–100) based on core skills, role alignment, domain experience, and seniority. Accept only vacancies with `match_score >= 60`.

---

## 6. PHASE 4 — UNIFIED DEDUPLICATION & CANONICALIZATION

Perform deduplication before every insertion against records created within the last 30 days (`created_at > datetime('now', '-30 days')`):

1. **URL Canonicalization**: Strip tracking parameters (`utm_*`, `ref`, `fbclid`), URL fragments, and trailing slashes from `submit_url`. Never canonicalize using LinkedIn post permalinks, search URLs, or profile URLs.
2. **Deduplication Check**:
   * If a matching canonical `submit_url` exists in `/runtime/workspace/app.db.work`, refresh source-owned fields and set `status='updated'`.
   * If identical normalized text or identical role/company/location exists under another URL created within 30 days, skip insertion.

---

## 7. PHASE 5 — STRUCTURED EXTRACTION & PERSISTENCE

### Standardized Structured Summary (`vacancy.text`)
`vacancy.text` must be a concise structured summary derived only after reading the expanded post. Do not paste raw marketing text, emojis, hashtags, biographies, or URLs.

Use this exact 8-line plain-text template (omit a line only if not stated):
```text
Employer: <company or "Not stated">
Role: <exact vacancy title>
Employment: <type, if stated>
Location: <location/remote/hybrid conditions>
Responsibilities: <concise semicolon-separated facts>
Requirements: <concise semicolon-separated facts>
Visa/work authorization: <stated condition or "Not stated">
Application instructions: <how to apply, excluding raw submit URL/email>
```

### Contact Rules
* `submit_email`: Syntactically valid recruiter/application email, or `NULL`.
* `submit_url`: Verified ATS/application form destination URL, or `NULL`.
* At least one of `submit_email` or `submit_url` MUST be non-NULL. Never store post permalinks, profile URLs, or search URLs in either field.

### Database Persistence
Persist accepted vacancies into `vacancy` table in `/runtime/workspace/app.db.work` using parameterized SQL inside a transaction:
```sql
INSERT INTO vacancy (title, text, submit_email, submit_url, source, visa_status, status, deleted)
VALUES (:title, :text, :submit_email, :submit_url, 'LinkedIn', 'NOT_SPECIFIED', 'created', 0);
```
Track created/updated row IDs during the current run.

---

## 8. PHASE 6 — AUDIT, PUBLISH & REPORT

1. **Post-Insertion Audit**: Query all rows created/updated in current run and verify non-empty role title, valid 8-line structured text, valid contact credentials, 30-day freshness, and score >= 60. Delete any row failing audit.
2. **Atomic Publish**: Execute the Atomic Publication Protocol (Section 2) to update `/runtime/harness-scraper/app.db`.
3. **Execution Report**: Output a concise summary containing read profile files, candidate summary, search queries run, posts inspected, rejection counts by gate, and IDs/titles of final saved vacancies.
