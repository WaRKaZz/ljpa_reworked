# AUTOMATED REUSABLE SITE SKILL SAVING HARNESS

## OBJECTIVE

Refactor and persist technical reusable site automation knowledge learned during the application submission in this conversation.

Your tasks:
1. Create or update a dedicated technical skill file at `/runtime/workspace/<site-or-vacancy-name>/SKILL.md`.
2. Register the URL domain or pattern mapping in `/runtime/workspace/README.md`.

---

## 1. TECHNICAL REUSABLE SITE KNOWLEDGE ONLY

Inside `/runtime/workspace/<site-or-vacancy-name>/SKILL.md`:
* Document clear, step-by-step technical instructions for automating job applications on this portal/ATS.
* Include selector strategies, modal dismissal rules, navigation shortcuts, file upload handling, and direct apply URL patterns.
* Focus exclusively on reproducible site mechanics and workflow patterns.

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
