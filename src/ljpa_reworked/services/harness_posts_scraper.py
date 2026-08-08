import logging
import os
from typing import Any

from playwright.async_api import Page, async_playwright

from ljpa_reworked.models.database_models import LinkedinPost
from ljpa_reworked.operations.linkedin_post_ops import save_linkedin_post

logger = logging.getLogger(__name__)

DEFAULT_CDP_URL = os.getenv("CDP_URL", "http://cloak-browser:9222")


import re

def is_valid_job_post(text: str, url: str | None) -> tuple[bool, str | None]:
    """
    Strict Guard-Rail Validator:
    Returns (is_valid, extracted_credentials).
    A post is ONLY valid if:
    1. It has a non-empty, valid URL.
    2. It is not UI noise (e.g., profile snippets, ads, analytics).
    3. It contains valid recruiter contact credentials (email or explicit application link).
    """
    if not url or not isinstance(url, str) or not url.startswith("http"):
        return False, None

    if not text or len(text.strip()) < 40:
        return False, None

    # Filter out common UI noise text
    noise_keywords = [
        "view all analytics", "profile viewers", "act now: 1 month of free premium",
        "start a post", "see how premium helps", "connect with", "followers"
    ]
    lower_text = text.lower()
    if any(k in lower_text for k in noise_keywords):
        return False, None

    # Extract email or contact credentials
    email_match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
    link_match = re.search(r"https?://lnkd\.in/[a-zA-Z0-9_-]+", text)

    credentials = None
    if email_match:
        credentials = email_match.group(0)
    elif link_match:
        credentials = f"Apply via link: {link_match.group(0)}"
    elif "contact" in lower_text or "apply" in lower_text or "dm" in lower_text:
        credentials = "Direct contact via recruiter post"

    if not credentials:
        return False, None

    return True, credentials


async def extract_posts_from_feed(page: Page, max_posts: int = 10) -> list[dict[str, Any]]:
    """
    Extract post text and permalink URL from feed update elements on the LinkedIn feed page.
    Scrolls down to trigger lazy-loaded feed content and applies strict Guard-Rail filtering.
    """
    posts: list[dict[str, Any]] = []

    # Scroll to trigger feed post rendering
    for _ in range(5):
        try:
            await page.evaluate("window.scrollBy(0, 1000)")
            await page.wait_for_timeout(1000)
        except Exception as e:
            logger.debug(f"Scroll iteration warning: {e}")

    locators = [
        "main#workspace div[componentkey]",
        "main div[componentkey]",
        "div.feed-shared-update-v2",
        "div.occludable-update",
        "div[data-id*='urn:li:activity']",
        "article",
        "div.feed-shared-post",
    ]

    found_elements = []
    for loc_str in locators:
        loc = page.locator(loc_str)
        cnt = await loc.count()
        if cnt > 0:
            for i in range(cnt):
                found_elements.append(loc.nth(i))
            break

    seen_texts = set()
    for elem in found_elements:
        if len(posts) >= max_posts:
            break
        text = ""
        url = None

        try:
            raw_text = await elem.inner_text()
            text = raw_text.strip() if raw_text else ""
        except Exception as e:
            logger.warning(f"Error reading inner_text for post element: {e}")

        if not text or text in seen_texts:
            continue

        try:
            link_loc = elem.locator("a.app-aware-link[href*='/feed/update/'], a[href*='/posts/'], a[href*='/recent-activity/']")
            if await link_loc.count() > 0:
                url = await link_loc.first.get_attribute("href")
        except Exception as e:
            logger.warning(f"Error extracting update URL: {e}")

        is_valid, credentials = is_valid_job_post(text, url)
        if not is_valid:
            logger.debug("Post discarded by Guard-Rail check (missing valid URL, credentials, or text noise).")
            continue

        seen_texts.add(text)
        posts.append({"text": text, "url": url, "credentials": credentials})

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
        await page.wait_for_timeout(3000)

        extracted_posts = await extract_posts_from_feed(page, max_posts=max_posts)
        logger.info(f"Extracted {len(extracted_posts)} post(s) passing strict Guard-Rails.")

        for p_dict in extracted_posts:
            post_record = save_linkedin_post(text=p_dict.get("text", ""), url=p_dict.get("url"))
            saved_posts.append(post_record)

    return saved_posts


import subprocess

def run_agy_harness_1(prompt: str | None = None, container_name: str = "antigravity-cli-dev") -> str:
    """
    Harness 1 AGY Agent Runner:
    Delegates post searching and navigation task to the Google Antigravity SDK (`agy` CLI) agent
    running inside the dedicated container harness with strict Guard-Rails.
    """
    default_prompt = (
        "STRICT GUARD-RAILS & NON-NEGOTIABLE VALIDATION RULES:\n"
        "1. Read the candidate personal profile from resources/profile.md. Meticulously analyze skills and experience.\n"
        "2. Dynamically expand candidate target job titles based strictly on profile skills (PLC, SCADA, Automation, Control Systems).\n"
        "3. Connect to CloakBrowser CDP at http://cloak-browser:9222 and navigate the LinkedIn posts feed.\n"
        "4. FOR EVERY POST EVALUATED:\n"
        "   - RULE A (MANDATORY URL): The post MUST have a valid, direct permalink URL. If URL is missing or invalid, DISCARD post immediately.\n"
        "   - RULE B (MANDATORY CREDENTIALS/EMAIL): The post MUST contain recruiter contact credentials (email address, direct apply link, or explicit contact method). If missing, DISCARD post immediately.\n"
        "   - RULE C (NO NOISE): Do NOT save generic UI elements, profile widgets, ads, or posts without vacancy details. Skip them and move to next post.\n"
        "5. For valid posts meeting ALL guard-rails, save directly into SQLite database data/app.db following ORM schema:\n"
        "   - 'vacancy' table: title (String 200), text (Text), credentials (String 500 - mandatory email/contact), url (String 200 - mandatory permalink), source='LinkedIn', visa_status='NOT_SPECIFIED', processed=False, deleted=False.\n"
        "   - 'linkedin_post' table: text (Text), url (Text - mandatory permalink), vacancy_id (Integer ForeignKey 'vacancy.id'), processed=False, deleted=False.\n"
        "Be extremely thoughtful, meticulous, and strict. Do not save any record unless both URL and contact credentials exist."
    )
    task_prompt = prompt or default_prompt
    logger.info("Triggering Harness 1 agy agent in container '%s' with strict Guard-Rails...", container_name)

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
