import json
import logging
import os
from getpass import getpass
from time import sleep

from pydantic import BaseModel
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PostData(BaseModel):
    text: str
    screenshot: bytes
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
        return webdriver.Remote(
            command_executor=SELENIUM_COMMAND_EXECUTOR, options=options
        )

    @staticmethod
    def _get_credentials() -> tuple[str, str]:
        email = os.getenv("LINKEDIN_EMAIL") or input("LinkedIn email: ")
        password = os.getenv("LINKEDIN_PASSWORD") or getpass("LinkedIn password: ")
        return email, password

    def _save_cookies(self) -> None:
        with open(self.COOKIES_PATH, "w") as file:
            json.dump(self.driver.get_cookies(), file)

        logger.info("Cookies saved to %s", self.COOKIES_PATH)

    def _load_cookies(self) -> None:
        if os.path.exists(self.COOKIES_PATH):
            with open(self.COOKIES_PATH) as file:
                cookies = json.load(file)
                for cookie in cookies:
                    self.driver.add_cookie(cookie)

    def _scroll_down(self, pause: float = 2.0, max_scrolls: int = 10) -> None:
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        for _ in range(max_scrolls):
            self.driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight);"
            )
            sleep(pause)
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

    def _get_post_url(self, post) -> str:
        try:
            element = post.find_element(By.XPATH, ".//div/div/div/a")
            href = element.get_attribute("href")
            clean_href = href.split("?")[0]
            if "company" in clean_href or "showcase" in clean_href:
                return clean_href
            else:
                return clean_href + "/recent-activity/all/"
        except Exception as e:
            logger.error(
                f"Error finding LinkedIn profile link: {e}"
            )  # TODO: Review if this logger is necessary.
            return None

    def _capture_screenshot(self) -> None:
        self.driver.save_screenshot(self.SCREENSHOT_PATH)
        logger.error(
            "Screenshot saved to %s", self.SCREENSHOT_PATH
        )  # TODO: Review if this logger is necessary.

    def _input_credentials(self, email: str, password: str) -> None:
        self.wait.until(EC.presence_of_element_located((By.ID, "username"))).send_keys(
            email
        )
        self.driver.find_element(By.ID, "password").send_keys(password)
        self.driver.find_element(By.XPATH, "//button[@type='submit']").click()

    def _check_login_success(self) -> bool:
        self.wait.until(
            lambda d: "feed" in d.current_url or "checkpoint/challenge" in d.current_url
        )
        if "checkpoint/challenge" in self.driver.current_url:
            logger.warning(
                "Two-factor authentication required! Please complete verification."
            )  # TODO: Review if this logger is necessary.
            sleep(360)
        return "feed" in self.driver.current_url

    def login(self) -> bool:
        try:
            self.driver.get(self.LOGIN_URL)
            self._load_cookies()
            self.driver.refresh()
            if "feed" in self.driver.current_url:
                logger.info(
                    "Already logged in."
                )  # TODO: Review if this logger is necessary.
                return True
            email, password = self._get_credentials()
            self._input_credentials(email, password)
            if self._check_login_success():
                self._save_cookies()
                logger.info(
                    "Login successful!"
                )  # TODO: Review if this logger is necessary.
                return True
            return False
        except Exception as err:
            logger.error(
                "Login failed: %s", err
            )  # TODO: Review if this logger is necessary.
            self._capture_screenshot()
            return False

    def _expand_post(self, post) -> None:
        try:
            more_button = post.find_element(
                By.CSS_SELECTOR,
                ".feed-shared-inline-show-more-text__see-more-less-toggle > span",
            )
            self.driver.execute_script("arguments[0].click();", more_button)
        except NoSuchElementException:
            pass

    def search_posts(self, max_posts: int = 20) -> list[PostData] | None:
        try:
            self.driver.get(self.SEARCH_URL)
            self._scroll_down(pause=3.0, max_scrolls=15)
            sleep(5)
            posts_elements = self.driver.find_elements(
                By.CLASS_NAME, "fie-impression-container"
            )
            posts_data = []
            for post in posts_elements[:max_posts]:
                url = self._get_post_url(post)
                self._expand_post(post)
                posts_data.append(
                    PostData(
                        text=post.text,
                        screenshot=post.screenshot_as_png,
                        url=url,
                    )
                )
            return posts_data
        except Exception as err:
            logger.error(
                "Failed to search posts: %s", err
            )  # TODO: Review if this logger is necessary.
            self._capture_screenshot()
            return None

    def get_vacancies(self) -> list[PostData] | None:
        if self.login():
            posts = self.search_posts()
            self.close()
            return posts
        return None

    def close(self) -> None:
        self.driver.quit()
