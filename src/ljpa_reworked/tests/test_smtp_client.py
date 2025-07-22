import unittest

from ljpa_reworked.config import (
    EMAIL_SIGNATURE,
    SMTP_EMAIL,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_SERVER,
)
from ljpa_reworked.services.smtp_client import SMTPClient


class TestSMTPClient(unittest.TestCase):
    def test_send_email(self):
        """
        Test sending an email using SMTPClient.
        """
        if not all([SMTP_EMAIL, SMTP_PASSWORD, SMTP_SERVER, SMTP_PORT]):
            self.skipTest("SMTP credentials are not configured.")

        config = {
            "email": SMTP_EMAIL,
            "password": SMTP_PASSWORD,
            "smtp_server": SMTP_SERVER,
            "smtp_port": int(SMTP_PORT),
        }

        try:
            with SMTPClient(config) as client:
                client.send_email(
                    to=SMTP_EMAIL,  # Sending to self for testing
                    subject="Test Email from LJPA Reworked",
                    body=f"This is a test email.\n\n{EMAIL_SIGNATURE}",
                )
        except Exception as e:
            self.fail(f"SMTPClient.send_email() raised an exception: {e}")


if __name__ == "__main__":
    unittest.main()
