import logging
import os
from typing import Any

from playwright.async_api import Page, async_playwright

from ljpa_reworked.models.database_models import LinkedinPost
from ljpa_reworked.operations.linkedin_post_ops import save_linkedin_post

logger = logging.getLogger(__name__)

DEFAULT_CDP_URL = os.getenv("CDP_URL", "http://cloak-browser:9222")


async def extract_posts_from_feed(page: Page, max_posts: int = 10) -> list[dict[str, Any]]:
    """
    Extract post text and permalink URL from feed update elements on the LinkedIn feed page.
    """
    posts: list[dict[str, Any]] = []
    post_elements = page.locator("div.feed-shared-update-v2, div.occludable-update")
    count = await post_elements.count()

    for i in range(min(count, max_posts)):
        elem = post_elements.nth(i)
        text = ""
        url = None

        try:
            raw_text = await elem.inner_text()
            text = raw_text.strip() if raw_text else ""
        except Exception as e:
            logger.warning(f"Error reading inner_text for post element {i}: {e}")

        try:
            link_loc = elem.locator("a.app-aware-link[href*='/feed/update/']")
            if await link_loc.count() > 0:
                url = await link_loc.first.get_attribute("href")
        except Exception as e:
            logger.warning(f"Error extracting update URL for post element {i}: {e}")

        if text or url:
            posts.append({"text": text, "url": url})

    return posts


async def run_posts_scraper(cdp_url: str | None = None, max_posts: int = 10) -> list[LinkedinPost]:
    """
    Harness 1: Autonomous LinkedIn Posts Feed Scraper.
    Connects to browser over CDP, navigates to feed, extracts vacancy posts, and persists them into SQLite.
    """
    endpoint = cdp_url or os.getenv("CDP_URL", DEFAULT_CDP_URL)

    saved_posts: list[LinkedinPost] = []
    async with async_playwright() as p:
        logger.info(f"Harness 1 connecting to CDP endpoint: {endpoint}")
        browser = await p.chromium.connect_over_cdp(endpoint)
        context = browser.contexts[0] if browser.contexts else await browser.new_context()

        # Load auth cookies if state file exists
        from ljpa_reworked.auth.session import DEFAULT_STATE_PATH, verify_auth_state, load_auth_state
        if verify_auth_state(DEFAULT_STATE_PATH):
            try:
                state = load_auth_state(DEFAULT_STATE_PATH)
                await context.add_cookies(state.get("cookies", []))
                logger.info("Loaded auth state cookies into Playwright context.")
            except Exception as e:
                logger.warning(f"Could not load cookies from state file: {e}")

        page = context.pages[0] if context.pages else await context.new_page()

        logger.info("Navigating to https://www.linkedin.com/feed/ ...")
        await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")

        extracted_posts = await extract_posts_from_feed(page, max_posts=max_posts)
        logger.info(f"Extracted {len(extracted_posts)} post(s) from feed.")

        for p_dict in extracted_posts:
            post_record = save_linkedin_post(text=p_dict.get("text", ""), url=p_dict.get("url"))
            saved_posts.append(post_record)

    return saved_posts


import subprocess

def run_agy_harness_1(prompt: str | None = None, container_name: str = "antigravity-cli-dev") -> str:
    """
    Harness 1 AGY Agent Runner:
    Delegates post searching and navigation task to the Google Antigravity SDK (`agy` CLI) agent
    running inside the dedicated container harness.
    """
    default_prompt = (
        "1. Read the candidate personal profile from resources/profile.md. Analyze key skills, tech stack, and experience.\n"
        "2. Dynamically extract and expand all potential matching target job titles based strictly on the candidate's skills and experience in resources/profile.md.\n"
        "3. Connect to CloakBrowser CDP at http://cloak-browser:9222 and navigate the LinkedIn posts feed.\n"
        "4. Extract the 10 most recent posts with high skills matching against the candidate profile.\n"
        "5. Save extracted vacancies directly into the SQLite database data/app.db following this exact ORM schema:\n"
        "   - 'vacancy' table: title (String 200), text (Text - full post text), credentials (String 500 - contact email/HR info), url (String 200 - post permalink), source='LinkedIn', visa_status='NOT_SPECIFIED', processed=False, deleted=False.\n"
        "   - 'linkedin_post' table: text (Text), url (Text), vacancy_id (Integer ForeignKey 'vacancy.id'), processed=False, deleted=False.\n"
        "Ensure all extracted records are normalized and saved into SQLite data/app.db."
    )
    task_prompt = prompt or default_prompt
    logger.info("Triggering Harness 1 agy agent in container '%s'...", container_name)

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
