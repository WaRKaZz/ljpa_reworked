from unittest.mock import MagicMock, patch

import pytest
import requests

from ljpa_reworked.services.telegram import Telegram


def test_telegram_init_missing_config_raises_value_error():
    with patch("ljpa_reworked.services.telegram.TELEGRAM_BOT_TOKEN", None):
        with patch("ljpa_reworked.services.telegram.TELEGRAM_CHAT_ID", None):
            with pytest.raises(ValueError, match="is not set"):
                Telegram()


def test_telegram_send_message_success():
    with patch("ljpa_reworked.services.telegram.TELEGRAM_BOT_TOKEN", "mock_token"):
        with patch("ljpa_reworked.services.telegram.TELEGRAM_CHAT_ID", "12345"):
            tg = Telegram()

    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None

    with patch("requests.post", return_value=mock_resp) as mock_post:
        res = tg.send_message("Test message")

    assert res is True
    mock_post.assert_called_once_with(
        "https://api.telegram.org/botmock_token/sendMessage",
        data={"chat_id": "12345", "text": "Test message"},
    )


def test_telegram_send_message_failure():
    with patch("ljpa_reworked.services.telegram.TELEGRAM_BOT_TOKEN", "mock_token"):
        with patch("ljpa_reworked.services.telegram.TELEGRAM_CHAT_ID", "12345"):
            tg = Telegram()

    with patch(
        "requests.post",
        side_effect=requests.exceptions.RequestException("Network error"),
    ):
        res = tg.send_message("Test message")

    assert res is False


def test_telegram_send_image_success(tmp_path):
    with patch("ljpa_reworked.services.telegram.TELEGRAM_BOT_TOKEN", "mock_token"):
        with patch("ljpa_reworked.services.telegram.TELEGRAM_CHAT_ID", "12345"):
            tg = Telegram()

    img_file = tmp_path / "test.png"
    img_file.write_bytes(b"png data")

    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None

    with patch("requests.post", return_value=mock_resp) as mock_post:
        res = tg.send_image(str(img_file), caption="Test image")

    assert res is True
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert call_args[0][0] == "https://api.telegram.org/botmock_token/sendPhoto"
    assert call_args[1]["data"] == {"chat_id": "12345", "caption": "Test image"}
    assert "photo" in call_args[1]["files"]


def test_telegram_send_image_file_not_found():
    with patch("ljpa_reworked.services.telegram.TELEGRAM_BOT_TOKEN", "mock_token"):
        with patch("ljpa_reworked.services.telegram.TELEGRAM_CHAT_ID", "12345"):
            tg = Telegram()

    res = tg.send_image("nonexistent_file_path.png")
    assert res is False
