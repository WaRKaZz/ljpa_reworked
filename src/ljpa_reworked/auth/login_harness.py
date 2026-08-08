import asyncio
import os
from playwright.async_api import async_playwright

async def check_login_success(page, context):
    """Background check for successful login."""
    while True:
        try:
            # Check if elements accessible only after login have appeared
            # .global-nav__me is the profile icon dropdown on LinkedIn
            if await page.locator(".global-nav__me").count() > 0:
                print("Successful login detected!")
                # Ensure the auth directory exists
                os.makedirs("auth", exist_ok=True)
                await context.storage_state(path="auth/state.json")
                return True
        except Exception as e:
            print(f"Error during login check: {e}")
        
        await asyncio.sleep(5)  # Check every 5 seconds

async def main():
    async with async_playwright() as p:
        # Determine if we should connect to a remote Selenium container (via CDP) or launch locally
        remote_url = os.getenv("CDP_URL")  # e.g. "http://selenium:4444"
        
        if remote_url:
            print(f"Connecting to remote browser at {remote_url}")
            browser = await p.chromium.connect_over_cdp(remote_url)
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = context.pages[0] if context.pages else await context.new_page()
        else:
            print("Launching local browser in headed mode...")
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()

        print("Navigating to LinkedIn login page...")
        await page.goto("https://www.linkedin.com/login")
        print("Please complete the login and 2FA via VNC/browser window.")

        try:
            # Wait for up to 1 hour (3600 seconds) for the user to log in manually
            await asyncio.wait_for(check_login_success(page, context), timeout=3600)
            print("Login successful and state saved to auth/state.json.")
        except asyncio.TimeoutError:
            print("Authorization timeout (1 hour reached). No successful login detected.")
        except Exception as e:
            print(f"Unexpected error: {e}")
        finally:
            print("Closing browser...")
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
