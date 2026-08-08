import logging
import subprocess

logger = logging.getLogger(__name__)


def run_agy_harness_1(prompt: str | None = None, container_name: str = "antigravity-cli-dev") -> str:
    """
    Harness 1 AGY Agent Runner:
    Delegates post searching and navigation task to the Google Antigravity SDK (`agy` CLI) agent
    running inside the dedicated container harness with strict Guard-Rails and Self-Verification audit loop.
    """
    default_prompt = (
        "/goal DEPERSONALIZED LINKEDIN POST VACANCY DISCOVERY & SELF-AUDIT HARNESS\n\n"
        "OBJECTIVE:\n"
        "Discover, validate, deduplicate, and persist up to 10 fresh, high-quality job vacancies matching candidate profile skills into SQLite database data/app.db.\n\n"
        "MANDATORY TOOLING:\n"
        "Must use MCP Unbrowse (mcp-unbrowse / Playwright connected to http://cloak-browser:9222) for all browser actions.\n\n"
        "PHASE 1: DYNAMIC PROFILE INGESTION\n"
        "1. Read candidate profile files in the resources/ directory (e.g. resources/profile.md).\n"
        "2. Dynamically extract candidate technical skills, domain experience, and matching job roles. Do NOT hardcode any candidate name or specific role titles.\n\n"
        "PHASE 2: LINKEDIN FEED SCRAPING & 30-DAY DEDUPLICATION\n"
        "3. Connect to http://cloak-browser:9222 via mcp-unbrowse and navigate to LinkedIn feed (https://www.linkedin.com/feed/).\n"
        "4. Perform up to 3 scroll and extraction passes on the feed.\n"
        "5. FOR EVERY POST EVALUATED, APPLY NON-NEGOTIABLE GUARD-RAILS:\n"
        "   - 30-DAY DEDUPLICATION: Query SQLite database data/app.db. If post URL or identical vacancy text exists in 'vacancy' or 'linkedin_post' tables within the last 30 days (created_at > datetime('now', '-30 days')), SKIP IMMEDIATELY.\n"
        "   - MANDATORY CREDENTIALS: The post MUST contain a valid recruiter contact email address OR explicit application link (lnkd.in / external form). Discard posts lacking recruiter contact credentials.\n"
        "   - URL FLEXIBILITY: Direct permalink URL is preferred; if missing, author profile URL or email-verified post text is accepted.\n"
        "   - SEMANTIC RELEVANCE: Ensure qualitative alignment with candidate skills extracted dynamically from resources/ directory.\n"
        "6. Persist valid vacancies directly into SQLite database data/app.db:\n"
        "   - 'vacancy' table: title, text, credentials, url, source='LinkedIn', visa_status='NOT_SPECIFIED', processed=False, deleted=False.\n"
        "   - 'linkedin_post' table: text, url, vacancy_id, processed=False, deleted=False.\n\n"
        "PHASE 3: SELF-VERIFICATION & POST-AUDIT CLEANUP LOOP\n"
        "7. Query saved records in SQLite database data/app.db.\n"
        "8. Inspect each newly saved row: verify credentials (email/apply link) and mandatory fields. Execute SQL DELETE for any invalid or incomplete rows.\n"
        "9. If total valid count is less than 10 after cleanup, continue feed extraction up to 3 passes maximum. If after 3 passes fewer than 10 are found, finalize with all valid saved records.\n\n"
        "COMPLETION CRITERIA:\n"
        "Stop execution when 10 fresh, 30-day deduplicated, audited vacancies are persisted in SQLite data/app.db (or after 3 full passes)."
    )
    task_prompt = prompt or default_prompt
    logger.info("Triggering Harness 1 agy agent in container '%s' with strict Guard-Rails and Self-Verification...", container_name)

    cmd = [
        "podman",
        "exec",
        container_name,
        "agy",
        "--print",
        "--print-timeout",
        "15m",
        "--dangerously-skip-permissions",
        task_prompt,
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return res.stdout
    except subprocess.CalledProcessError as e:
        logger.error("Error executing agy harness in container: %s", e.stderr)
        raise
