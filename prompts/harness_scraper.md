# LINKEDIN DIRECT VACANCY DISCOVERY, VALIDATION, PERSISTENCE & SELF-AUDIT (REFACTORED V3)

## OBJECTIVE

Discover, validate, deduplicate, and persist up to 10 fresh, high-quality LinkedIn vacancies matching the candidate profile into a disposable workspace copy of the canonical database (`/runtime/workspace/app.db.work`). Replace the canonical database (`/runtime/harness-scraper/app.db`) atomically only after all post-insertion audits succeed.

Search LinkedIn posts only. Do not analyze the home feed, use direct messages, or apply to jobs.

---

## 1. BROWSER SETUP & BROWSER USE MCP DELEGATION MODEL

All browser execution is delegated through the **Browser Use MCP** server (`browser_use`).

### Responsibility Model
* **Antigravity (Orchestrator)**: Decides *what* search queries to run, what candidate posts to inspect, evaluates semantic matching against the profile, verifies gates, deduplicates records, and manages database transactions.
* **Browser Use (Browser Executor)**: Autonomously executes complete browser goals (navigating LinkedIn, scrolling feeds, expanding "See more", unwrapping external ATS redirect links, and extracting text/contacts) and returns structured results.

### Tool Usage Protocol
1. **High-Level Goal Delegation**: Call Browser Use MCP (`run_browser_task` or `browse_url`) with clear, self-contained objectives rather than issuing low-level step-by-step clicks or DOM queries.
2. **Compact Result Consumption**: Antigravity consumes the structured output/report returned by Browser Use. Do not request or process raw browser step traces unless diagnosing a failure.
3. **Legacy Fallback**: Legacy browser tools (`unbrowse`, `playwright`) are reserved strictly as emergency fallbacks if Browser Use encounters an unrecoverable transport error. Antigravity must never default to micromanaging DOM actions.

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

1. Inspect candidate profile resources at `/inputs/resources/profile.md` (or `resources/profile.md`).
2. Dynamically extract location, visa/work authorization constraints, acceptable work arrangements (remote/hybrid/onsite), technical skills, domain experience, role families, and seniority.
3. Build a concise internal candidate profile summary. Do not hardcode candidate names, locations, technologies, or titles.

---

## 4. PHASE 2 — DYNAMIC SEARCH STRATEGY

Generate up to 3 search passes dynamically from candidate profile:
* **PASS 1 — HIGH PRECISION**: Core role family + primary skills + vacancy intent terms (`hiring`, `vacancy`, `opening`, `apply`, `recruiter email`).
* **PASS 2 — ALTERNATIVE MATCHES**: Profile-derived role synonyms + domain terms + secondary skills.
* **PASS 3 — CONTROLLED BROADENING**: Broader queries while retaining key profile skills/domain constraints.

### Delegated Search Execution
For each pass, instruct Browser Use via a high-level goal:
```text
Navigate to LinkedIn post search with query "<generated_query>".
Scroll through the search results for up to 3 scroll cycles.
Collect candidate vacancy posts, extracting the author, post snippet, post permalink, and any immediately visible contact credentials.
```
Search LinkedIn posts only. Stop immediately once 10 fully validated vacancies pass final audit.

---

## 5. PHASE 3 — CANDIDATE EVALUATION & MANDATORY GATES

### Delegated Post Inspection Requirement
A search snippet is metadata only. For each prospective vacancy:
1. Delegate post inspection to Browser Use:
   ```text
   Open LinkedIn post at "<post_url>".
   Expand the full post body by clicking "See more".
   If the post contains an external application link or job link with an "Apply" button, follow/click it to unwrap all redirects and return the final destination ATS URL.
   Extract the full post text, company name, role title, location/remote conditions, requirements, recruiter email, and final application URL.
   ```
2. Antigravity evaluates the returned facts against the mandatory gates:

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
