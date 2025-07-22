import os
import unittest

from ljpa_reworked.config import SCREENSHOTS_DIR, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from ljpa_reworked.services.telegram import Telegram


class TestTelegram(unittest.TestCase):
    def setUp(self):
        """
        Set up the test case.
        """
        if not all([TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]):
            self.skipTest("Telegram credentials are not configured.")
        self.telegram = Telegram()

    def test_send_message(self):
        """
        Test sending a message using Telegram.
        """
        try:
            result = self.telegram.send_message(
                "Test message from LJPA Reworked test suite."
            )
            self.assertTrue(result, "Failed to send message.")
        except Exception as e:
            self.fail(f"Telegram.send_message() raised an exception: {e}")

    def test_send_image(self):
        """
        Test sending an image using Telegram.
        """
        # Find an image in the screenshots directory
        image_path = None
        if os.path.exists(SCREENSHOTS_DIR) and os.listdir(SCREENSHOTS_DIR):
            for file_name in os.listdir(SCREENSHOTS_DIR):
                full_path = os.path.join(SCREENSHOTS_DIR, file_name)
                if os.path.isfile(full_path):
                    image_path = full_path
                    break

        if not image_path:
            self.skipTest(
                "No images found in the screenshots directory to test sending an image."
            )

        try:
            result = self.telegram.send_image(
                image_path, caption="Test image from LJPA Reworked."
            )
            self.assertTrue(result, "Failed to send image.")
        except Exception as e:
            self.fail(f"Telegram.send_image() raised an exception: {e}")


if __name__ == "__main__":
    unittest.main()
