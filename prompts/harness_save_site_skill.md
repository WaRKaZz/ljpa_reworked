# AUTOMATED REUSABLE SITE SKILL SAVING HARNESS (REFACTORED V3)

## OBJECTIVE

Refactor and persist technical, reusable site automation knowledge learned during the Browser Use application submission in this conversation.

Your tasks:
1. Create or update a dedicated technical skill file at `/runtime/workspace/<site-or-vacancy-name>/SKILL.md` when new reusable knowledge or repair details are discovered.
2. Register the URL domain or pattern mapping in `/runtime/workspace/README.md`.
3. If an existing site skill worked without issues and no new reusable mechanics were observed, do not rewrite or modify the existing skill file.

---

## 1. REUSABLE SITE MECHANICS & WORKFLOW EXTRACTION

When Browser Use completes an application or recovers from an ATS form challenge, extract concise, high-level technical knowledge:

### What to Document in `/runtime/workspace/<site-or-vacancy-name>/SKILL.md`
* **ATS / Portal Identity**: Apex domain, portal platform (e.g. Workday, Greenhouse, Lever, SmartRecruiters, Personio, Taleo), and URL patterns.
* **Technical selector strategies**: Stable field labels, button identifiers, and robust selector strategies where available.
* **Navigation & Shortcuts**: Direct apply links, multi-page progression order, login requirements, and skip conditions.
* **Form & Interaction Patterns**: Mandatory section order, dropdown behaviors, radio group groupings, custom widgets, and consent checkbox locations.
* **File Upload Handling**: Specific file upload handling and upload triggers (e.g. "Resume uploader input appears inside 'My Experience' tab").
* **Modal & Dialog Dismissal**: Modal dismissal rules, cookie banner handling, mandatory popups, or disclosure dialogs.
* **Submit Sequence & Verification**: Exact final button label/behavior and confirmation messages indicating successful receipt.
* **Failure & Recovery Observations**: Workarounds for validation errors or anti-bot layout shifts discovered during Browser Use execution.

### Avoid Raw Trace Dumping
* **Do NOT paste raw step dumps**: Never dump raw Browser Use step logs, DOM node IDs, pixel offsets, or raw transcript histories into `SKILL.md`.
* Distill observations into concise, actionable instructions that allow future Browser Use runs to complete without unnecessary trial-and-error.

Inside `/runtime/workspace/README.md`:
* Add or update an explicit mapping entry linking the target ATS domain/URL pattern to `/runtime/workspace/<site-or-vacancy-name>/SKILL.md`.

---

## 2. STRICT PRIVACY & DATA ISOLATION BOUNDARY

* **No Personal Data**: Never include candidate profile facts, contact info, names, addresses, emails, passwords, OTPs, session tokens, or raw transcript retention in `SKILL.md` or `README.md`.
* **Credential Vault**: If portal account credentials were created or updated during submission, store them ONLY in `/runtime/workspace/credentials.json`. Never duplicate credentials in skill documentation or public files.
* **No Raw Logs**: Do not copy raw stream transcripts, terminal logs, or sensitive form values into skill files.

---

## 3. NON-INTERFERENCE BOUNDARY

* Do not evaluate job fit or candidate eligibility.
* Do not decide or change application submission status.
* Do not access or query SQLite database files (`/runtime/harness-scraper/app.db` or `data/app.db`).
* Do not request review or send Telegram notifications.
* Finish execution cleanly once `SKILL.md` and `README.md` are saved.
