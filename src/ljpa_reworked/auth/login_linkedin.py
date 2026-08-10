import asyncio
import logging
import os
import socket
import sys
from pathlib import Path

from dotenv import load_dotenv
from playwright.async_api import BrowserContext, Page, async_playwright

load_dotenv()

# Force unbuffered stdout logging
sys.stdout.reconfigure(line_buffering=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", stream=sys.stdout)
logger = logging.getLogger(__name__)

DEFAULT_SAVE_PATH = Path("data/state.json")

def get_cdp_endpoint() -> str:
    """Returns the CDP endpoint HTTP/WS URL from env or defaults to http://localhost:9222?fingerprint=linkedin_seed."""
    url = os.getenv("CDP_URL", "http://localhost:9222?fingerprint=linkedin_seed")
    if not url.startswith("ws://") and not url.startswith("http://"):
        url = f"http://{url}"
    if "cloak-browser" in url:
        try:
            socket.gethostbyname("cloak-browser")
        except socket.gaierror:
            url = url.replace("cloak-browser", "localhost")
    if "fingerprint" not in url:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}fingerprint=linkedin_seed"
    return url

def clean_env_val(val: str | None) -> str:
    """Helper to strip enclosing quotes from env string values."""
    if not val:
        return ""
    val = val.strip()
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        return val[1:-1]
    return val

async def fill_login_form(page: Page, email: str, password: str) -> bool:
    """Fills the LinkedIn login credentials and submits the form using resilient :visible locators."""
    try:
        email_locator = page.locator("input[type='email']:visible, #username:visible, input[name='session_key']:visible")
        if await email_locator.count() > 0:
            logger.info("Found visible email field. Filling email from .env...")
            await email_locator.first.fill(email)

            password_locator = page.locator("input[type='password']:visible, #password:visible, input[name='session_password']:visible")
            await password_locator.first.fill(password)

            submit_btn = page.locator("button[type='submit']:visible, .btn__primary--large:visible")
            if await submit_btn.count() > 0:
                await submit_btn.first.click()
            else:
                await password_locator.first.press("Enter")
            logger.info("Credentials submitted successfully. Waiting for authentication / 2FA...")
            return True
    except Exception as e:
        logger.warning(f"Error filling login form: {e}")
    return False

async def check_login_success(
    page: Page,
    context: BrowserContext,
    state_path: str | Path = DEFAULT_SAVE_PATH,
    poll_interval: float = 2.0,
    timeout: float = 3600.0,
) -> bool:
    """Polls the browser page until logged-in navigation element or feed URL is present,
    then saves storage_state to state_path.
    """
    path = Path(state_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    start_time = asyncio.get_event_loop().time()

    while True:
        try:
            is_feed_url = "/feed" in page.url or "/in/" in page.url
            has_nav_element = (
                await page.locator(".global-nav__me, header.global-nav, button:has-text('Me')").count() > 0
            )

            if is_feed_url or has_nav_element:
                logger.info(f"Successful LinkedIn login detected on {page.url}!")
                await context.storage_state(path=str(path))
                logger.info(f"Session state successfully saved to '{path}'")
                return True
        except Exception as e:
            logger.debug(f"Checking login status: {e}")

        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed >= timeout:
            logger.error(f"Login timeout of {timeout} seconds reached.")
            return False

        await asyncio.sleep(poll_interval)

async def main(state_path: str | Path = DEFAULT_SAVE_PATH):
    save_path = Path(state_path)
    cdp_url = get_cdp_endpoint()
    email = clean_env_val(os.getenv("LINKEDIN_EMAIL"))
    password = clean_env_val(os.getenv("LINKEDIN_PASSWORD"))

    logger.info(f"Connecting to CloakBrowser container via CDP endpoint at {cdp_url}...")

    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp(cdp_url)
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = context.pages[0] if context.pages else await context.new_page()

            # Check if already logged in or needs login
            if "/feed" not in page.url:
                logger.info("Navigating to https://www.linkedin.com/login ...")
                await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")

                if email and password:
                    await fill_login_form(page, email, password)
                else:
                    logger.warning("LINKEDIN_EMAIL or LINKEDIN_PASSWORD missing in .env")

            logger.info("If 2FA or CAPTCHA appears, please complete it manually.")
            success = await check_login_success(page, context, state_path=save_path, timeout=3600.0)
            if success:
                logger.info(f"LinkedIn authentication state successfully saved to '{save_path}'!")
            else:
                logger.error("Authentication failed or timed out.")

            await browser.close()
            return success
        except Exception as e:
            logger.error(f"Error during CDP LinkedIn login: {e}")
            raise

if __name__ == "__main__":
    asyncio.run(main())
