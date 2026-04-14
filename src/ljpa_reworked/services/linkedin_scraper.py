import json
import logging
import os
from getpass import getpass
from time import sleep
from typing import List

from pydantic import BaseModel
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from ljpa_reworked.config import (
    LINKEDIN_SEARCH_URL,
    RESOURCES_DIR,
    SELENIUM_COMMAND_EXECUTOR,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class PostData(BaseModel):
    text: str
    screenshot: bytes | None = None
    url: str | None = None

    class Config:
        arbitrary_types_allowed = True


class LinkedInScraper:
    LOGIN_URL = "https://www.linkedin.com/login"
    SEARCH_URL = LINKEDIN_SEARCH_URL
    COOKIES_PATH = os.path.join(RESOURCES_DIR, "linkedin_cookies.json")
    SCREENSHOT_PATH = "/tmp/linkedin_error.png"

    def __init__(self) -> None:
        self.driver: WebDriver = self._configure_driver()
        self.wait = WebDriverWait(self.driver, 15)

    def _configure_driver(self) -> WebDriver:
        options = ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--remote-debugging-port=9222")
        options.add_argument("--verbose")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-extensions")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        return webdriver.Remote(command_executor=SELENIUM_COMMAND_EXECUTOR, options=options)

    @staticmethod
    def _get_credentials() -> tuple[str, str]:
        email = os.getenv("LINKEDIN_EMAIL") or input("LinkedIn email: ")
        password = os.getenv("LINKEDIN_PASSWORD") or getpass("LinkedIn password: ")
        return email.strip(), password.strip()

    def _save_cookies(self) -> None:
        os.makedirs(os.path.dirname(self.COOKIES_PATH), exist_ok=True)
        with open(self.COOKIES_PATH, "w") as file:
            json.dump(self.driver.get_cookies(), file)
        logger.info("Cookies saved to %s", self.COOKIES_PATH)

    def _load_cookies(self) -> None:
        if os.path.exists(self.COOKIES_PATH):
            with open(self.COOKIES_PATH) as file:
                for cookie in json.load(file):
                    try:
                        self.driver.add_cookie(cookie)
                    except Exception:
                        pass

    def _scroll_and_load(self, pause: float = 1.5) -> None:
        """Makes exactly 3 full scrolls down the page."""
        for _ in range(3):
            # Scroll down by exactly one full screen height
            self.driver.execute_script("window.scrollBy(0, window.innerHeight);")
            sleep(pause)


    def _expand_post(self, post_element) -> None:
        """Clicks 'See more' if the post text is truncated."""
        try:
            btn = post_element.find_element(By.CSS_SELECTOR, '[data-testid="expandable-text-button"]')
            self.driver.execute_script("arguments[0].click();", btn)
            sleep(0.3)
        except NoSuchElementException:
            pass

    def _get_post_url(self, post_element) -> str | None:
        """Extracts the author's profile or company page URL."""
        try:
            links = post_element.find_elements(By.CSS_SELECTOR, 'a[href*="/in/"], a[href*="/company/"]')
            for link in links:
                href = link.get_attribute("href")
                if href and "lipi=" not in href and "showcase" not in href:
                    return href.split("?")[0].rstrip("/")
        except Exception as e:
            logger.debug("Failed to extract post URL: %s", e)
        return None

    def login(self) -> bool:
        try:
            self.driver.get(self.LOGIN_URL)
            self._load_cookies()
            self.driver.refresh()
            if "feed" in self.driver.current_url:
                logger.info("Already logged in.")
                return True

            email, password = self._get_credentials()
            self.wait.until(EC.presence_of_element_located((By.ID, "username"))).send_keys(email)
            self.driver.find_element(By.ID, "password").send_keys(password)
            self.driver.find_element(By.XPATH, "//button[@type='submit']").click()

            self.wait.until(
                lambda d: "feed" in d.current_url or "checkpoint/challenge" in d.current_url
            )
            if "checkpoint/challenge" in self.driver.current_url:
                logger.warning("2FA/Checkpoint required. Please complete it manually. Waiting 60s...")
                sleep(60)

            if "feed" in self.driver.current_url:
                self._save_cookies()
                logger.info("Login successful!")
                return True
            return False
        except Exception as err:
            logger.error("Login failed: %s", err)
            self.driver.save_screenshot(self.SCREENSHOT_PATH)
            return False

    def search_posts(self, max_posts: int = 20) -> List[PostData]:
        try:
            self.driver.get(self.SEARCH_URL)
            sleep(3)
            self._scroll_and_load()

            # Filter only elements that actually contain post text
            post_elements = [
                el for el in self.driver.find_elements(By.CSS_SELECTOR, '[role="listitem"]')
                if el.find_elements(By.CSS_SELECTOR, '[data-testid="expandable-text-box"]')
            ]

            posts_data: List[PostData] = []
            for post in post_elements[:max_posts]:
                try:
                    self._expand_post(post)
                    text_box = post.find_element(By.CSS_SELECTOR, '[data-testid="expandable-text-box"]')
                    text = text_box.text.strip()
                    if not text:
                        continue

                    url = self._get_post_url(post)
                    try:
                        screenshot = post.screenshot_as_png
                    except Exception:
                        screenshot = None

                    posts_data.append(PostData(text=text, screenshot=screenshot, url=url))
                except Exception as e:
                    logger.debug("Skipped post due to extraction error: %s", e)
                    continue

            logger.info("✅ Extracted %d posts successfully.", len(posts_data))
            return posts_data
        except Exception as err:
            logger.error("❌ Failed to search posts: %s", err)
            self.driver.save_screenshot(self.SCREENSHOT_PATH)
            return []

    def get_vacancies(self) -> List[PostData]:
        if self.login():
            posts = self.search_posts()
            self.close()
            return posts
        logger.error("Aborting: Login failed.")
        return []

    def close(self) -> None:
        if self.driver:
            self.driver.quit()
