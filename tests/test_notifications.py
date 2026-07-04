# tests/test_notifications.py
from unittest.mock import MagicMock, patch

from src.auth import notifications


def test_send_email_returns_false_when_smtp_not_configured(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    assert notifications.send_email("someone@example.com", "subject", "body") is False


def test_send_email_returns_true_on_successful_send(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USERNAME", "bot@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")

    mock_server = MagicMock()
    with patch("smtplib.SMTP") as mock_smtp:
        mock_smtp.return_value.__enter__.return_value = mock_server
        assert notifications.send_email("someone@example.com", "subject", "body") is True
    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once_with("bot@example.com", "secret")
    mock_server.sendmail.assert_called_once()


def test_send_email_returns_false_when_smtp_raises(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USERNAME", "bot@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")

    with patch("smtplib.SMTP", side_effect=Exception("connection refused")):
        assert notifications.send_email("someone@example.com", "subject", "body") is False


def test_send_sms_returns_false_when_twilio_not_configured(monkeypatch):
    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
    assert notifications.send_sms("+919876543210", "body") is False


def test_send_sms_returns_true_on_successful_send(monkeypatch):
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC123")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "token123")
    monkeypatch.setenv("TWILIO_FROM_NUMBER", "+15550001111")

    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    with patch("requests.post", return_value=mock_response) as mock_post:
        assert notifications.send_sms("+919876543210", "body") is True
    mock_post.assert_called_once()


def test_send_sms_returns_false_when_request_raises(monkeypatch):
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC123")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "token123")
    monkeypatch.setenv("TWILIO_FROM_NUMBER", "+15550001111")

    with patch("requests.post", side_effect=Exception("network down")):
        assert notifications.send_sms("+919876543210", "body") is False
