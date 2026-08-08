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
        "MANDATORY REQUIREMENT: Use Unbrowse MCP (mcp-unbrowse / Playwright on http://cloak-browser:9222) for all browser actions.\n\n"
        "1. Read resources/profile.md. Extract candidate Ivan Danilov's skills (PLC, SCADA, Automation, Control Systems).\n"
        "2. Navigate LinkedIn search posts page via mcp-unbrowse to search for matching job vacancy posts.\n"
        "3. STRICT GUARD-RAILS: Only save posts that contain a valid permalink URL and recruiter contact email/link. Ignore profile widgets, ads, or posts missing contacts/URLs.\n"
        "4. Save valid vacancies into SQLite data/app.db ('vacancy' and 'linkedin_post' tables following SQLAlchemy schema).\n"
        "5. SELF-VERIFICATION AUDIT: Connect to SQLite data/app.db, verify saved rows, and SQL DELETE any incomplete/invalid records. Repeat searching until exactly 10 fully verified, valid vacancies meeting all Guard-Rails are saved."
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
