import logging

import requests

from ljpa_reworked.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class Telegram:
    """Handles sending messages and images via Telegram bot using simple HTTP requests."""

    def __init__(self):
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            raise ValueError("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is not set.")
        self.bot_token = TELEGRAM_BOT_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    def send_message(self, message: str) -> bool:
        """Sends a plain text message to Telegram."""
        url = f"{self.base_url}/sendMessage"
        data = {"chat_id": self.chat_id, "text": message}

        try:
            response = requests.post(url, data=data)
            response.raise_for_status()  # Raises an exception for bad status codes
            logger.info("Message sent successfully.")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send message: {e}")
            return False

    def send_image(self, image_path: str, caption: str = "") -> bool:
        """Sends an image with optional caption to Telegram."""
        url = f"{self.base_url}/sendPhoto"
        data = {"chat_id": self.chat_id, "caption": caption}

        try:
            with open(image_path, "rb") as image_file:
                files = {"photo": image_file}
                response = requests.post(url, data=data, files=files)
                response.raise_for_status()
                logger.info("Image sent successfully.")
                return True
        except FileNotFoundError:
            logger.error(f"Image file not found: {image_path}")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send image: {e}")
            return False
