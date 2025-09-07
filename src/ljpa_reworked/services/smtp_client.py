import logging
import os
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class SMTPClient:
    """SMTP client for sending emails with optional attachments.

    Example:
        config = {
            "email": "your_email@gmail.com",
            "password": "your_app_password",
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587
        }

        with SMTPClient(config) as client:
            client.send_email(
                to="recipient@example.com",
                subject="Test Email",
                body="This is a test message",
                attachment="document.pdf"
            )

    """

    def __init__(self, config: dict):
        self._server = config["smtp_server"]
        self._port = config["smtp_port"]
        self._user = config["email"]
        self._password = config["password"]
        self._connection = None

    def connect(self):
        try:
            self._connection = smtplib.SMTP(self._server, self._port)
            self._connection.starttls()
            self._connection.login(self._user, self._password)
        except Exception as e:
            logger.error(
                f"Error connecting to SMTP server: {e}"
            )  # TODO: Review if this logger is necessary.
            raise

    def disconnect(self):
        if self._connection:
            self._connection.quit()

    def send_email(self, to: str, subject: str, body: str, attachment: str = None):
        """Send email with optional attachment.

        Args:
            to (str): Recipient email address
            subject (str): Email subject
            body (str): Email body text
            attachment (str, optional): Path to file attachment

        """
        msg = MIMEMultipart()
        msg["From"] = self._user
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        if attachment and os.path.exists(attachment):
            try:
                with open(attachment, "rb") as file:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(file.read())
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f"attachment; filename={os.path.basename(attachment)}",
                )
                msg.attach(part)
            except Exception as e:
                logger.error(f"Failed to attach file {attachment}: {e}")
                raise

        try:
            self._connection.sendmail(self._user, to, msg.as_string())
            logger.info(f"Email sent to {to}")
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            raise

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Context manager exit."""
        self.disconnect()
