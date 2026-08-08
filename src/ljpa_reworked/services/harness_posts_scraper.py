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
        page = context.pages[0] if context.pages else await context.new_page()

        logger.info("Navigating to https://www.linkedin.com/feed/ ...")
        await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")

        extracted_posts = await extract_posts_from_feed(page, max_posts=max_posts)
        logger.info(f"Extracted {len(extracted_posts)} post(s) from feed.")

        for p_dict in extracted_posts:
            post_record = save_linkedin_post(text=p_dict.get("text", ""), url=p_dict.get("url"))
            saved_posts.append(post_record)

    return saved_posts
