import asyncio
import logging
import os
from pathlib import Path
from typing import Union
from playwright.async_api import async_playwright, BrowserContext, Page

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def get_cdp_endpoint() -> str:
    """Returns the CDP endpoint HTTP/WS URL from env or defaults to http://localhost:9222."""
    url = os.getenv("CDP_URL", "http://localhost:9222")
    if not url.startswith("ws://") and not url.startswith("http://"):
        url = f"http://{url}"
    return url

async def check_login_success(
    page: Page,
    context: BrowserContext,
    state_path: Union[str, Path] = "auth/state.json",
    poll_interval: float = 3.0,
    timeout: float = 3600.0,
) -> bool:
    """
    Polls the browser page until logged-in navigation element (.global-nav__me) is present,
    then saves storage_state to state_path.
    """
    path = Path(state_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    start_time = asyncio.get_event_loop().time()

    while True:
        try:
            # Check for LinkedIn profile dropdown indicating active session
            if await page.locator(".global-nav__me").count() > 0:
                logger.info("Successful LinkedIn login detected!")
                await context.storage_state(path=str(path))
                logger.info(f"Session state successfully persisted to {path}")
                return True
        except Exception as e:
            logger.debug(f"Transient error checking login selector: {e}")

        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed >= timeout:
            logger.error(f"Login timeout of {timeout} seconds reached.")
            return False

        await asyncio.sleep(poll_interval)

async def main():
    cdp_url = get_cdp_endpoint()
    logger.info(f"Connecting to CloakBrowser CDP endpoint at {cdp_url}...")

    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp(cdp_url)
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = context.pages[0] if context.pages else await context.new_page()

            logger.info("Navigating browser to https://www.linkedin.com/login...")
            await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
            logger.info("Please perform LinkedIn login / 2FA / CAPTCHA interactively via noVNC at http://localhost:6080")

            success = await check_login_success(page, context, state_path="auth/state.json", timeout=3600.0)
            if success:
                logger.info("Stage 1 Interactive LinkedIn Authentication complete.")
            else:
                logger.error("Stage 1 Interactive LinkedIn Authentication failed or timed out.")
        except Exception as e:
            logger.error(f"Error during LinkedIn login harness execution: {e}")
            raise

if __name__ == "__main__":
    asyncio.run(main())
