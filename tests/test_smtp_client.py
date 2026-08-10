from unittest.mock import MagicMock, patch

from ljpa_reworked.services.smtp_client import SMTPClient


def test_smtp_client_context_manager_and_send_email():
    config = {
        "email": "user@example.com",
        "password": "secretpassword",
        "smtp_server": "smtp.example.com",
        "smtp_port": 587,
    }

    mock_smtp_inst = MagicMock()

    with patch("smtplib.SMTP", return_value=mock_smtp_inst) as mock_smtp_cls:
        with SMTPClient(config) as client:
            client.send_email(
                to="recipient@example.com",
                subject="Test Subject",
                body="Test Body",
            )

    mock_smtp_cls.assert_called_once_with("smtp.example.com", 587)
    mock_smtp_inst.starttls.assert_called_once()
    mock_smtp_inst.login.assert_called_once_with("user@example.com", "secretpassword")
    mock_smtp_inst.sendmail.assert_called_once()
    call_args = mock_smtp_inst.sendmail.call_args[0]
    assert call_args[0] == "user@example.com"
    assert call_args[1] == "recipient@example.com"
    assert "Subject: Test Subject" in call_args[2]
    mock_smtp_inst.quit.assert_called_once()


def test_smtp_client_send_email_with_attachment(tmp_path):
    config = {
        "email": "sender@example.com",
        "password": "password",
        "smtp_server": "smtp.example.com",
        "smtp_port": 587,
    }

    attachment_file = tmp_path / "resume.pdf"
    attachment_file.write_bytes(b"dummy pdf content")

    mock_smtp_inst = MagicMock()

    with patch("smtplib.SMTP", return_value=mock_smtp_inst):
        with SMTPClient(config) as client:
            client.send_email(
                to="hr@example.com",
                subject="Application",
                body="Please find my resume attached.",
                attachment=str(attachment_file),
            )

    mock_smtp_inst.sendmail.assert_called_once()
    raw_message = mock_smtp_inst.sendmail.call_args[0][2]
    assert "Content-Disposition: attachment; filename=resume.pdf" in raw_message
