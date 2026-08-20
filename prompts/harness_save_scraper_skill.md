# AUTOMATED REUSABLE LINKEDIN SCRAPER SKILL SAVING HARNESS

## OBJECTIVE

Refactor and persist technical reusable LinkedIn scraper and post discovery automation knowledge learned during the search pass in this conversation.

Your tasks:
1. Create or update a dedicated technical skill file at `/runtime/workspace/linkedin_posts_scraper/SKILL.md`.
2. Register the skill in `/runtime/workspace/README.md`.

---

## 1. TECHNICAL REUSABLE SCRAPER KNOWLEDGE ONLY

Inside `/runtime/workspace/linkedin_posts_scraper/SKILL.md`:
* Document clear, step-by-step technical instructions, search filters, and selectors for scraping LinkedIn posts.
* Focus strictly on reusable scraping mechanics and DOM navigation discovered during the run.
* Include working search query templates and keyword patterns that yielded high-relevance vacancies.
* Document exact CSS/XPath/text selectors for post containers/cards, author metadata, post body text containers, "See more" expand triggers, and external apply buttons/links.
* Document redirect unwrapping mechanics and HTTP/DOM patterns for external ATS portals and shortened URLs (e.g. `lnkd.in` or tracking redirects).
* Include feed scrolling timings, pagination tricks, dynamic element wait thresholds, and modal/dialog dismissal selectors.
* When repairing or updating previously failed selectors, document the exact failure reason, obsolete selector, and verified working workaround.

Inside `/runtime/workspace/README.md`:
* Add or update an explicit registry entry mapping LinkedIn post scraping to `/runtime/workspace/linkedin_posts_scraper/SKILL.md`.

---

## 2. STRICT PRIVACY & DATA ISOLATION BOUNDARY

* **No Personal Data**: Never include candidate personal data, profile facts, contact info, names, addresses, emails, passwords, OTPs, session tokens, or raw transcript retention in `SKILL.md` or `README.md`.
* **No Raw Logs**: Do not copy raw stream transcripts, terminal logs, or full scraped post contents into skill files. Keep examples generalized and synthetic.
* **No Credentials**: Never store LinkedIn account passwords, credentials, session cookies, OTPs, or authentication secrets in `SKILL.md` or `README.md`.

---

## 3. NON-INTERFERENCE BOUNDARY

* Do not evaluate job fit or candidate eligibility.
* Do not decide or change application submission status or vacancy records.
* Do not access, query, or modify SQLite database files (`/runtime/harness-scraper/app.db`, `/runtime/workspace/app.db.work`, or `data/app.db`).
* Do not request review or send Telegram notifications.
* Finish execution cleanly once `SKILL.md` and `README.md` are saved.
