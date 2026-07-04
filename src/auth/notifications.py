"""
Delivery channels for the password-reset token: email via SMTP, SMS via
Twilio's REST API. Both are entirely optional — gated on env vars, exactly
like GOOGLE_MAPS_API_KEY elsewhere in this project — and both return a plain
bool rather than raising, so a caller can always fall back to showing the
token on-screen (dev mode) instead of leaving the user stuck when no
provider is configured or a send fails.
"""
import os
import smtplib
from email.mime.text import MIMEText

import requests

TWILIO_SMS_URL = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
REQUEST_TIMEOUT = 10


def send_email(to_email: str, subject: str, body: str) -> bool:
    host = os.environ.get("SMTP_HOST")
    username = os.environ.get("SMTP_USERNAME")
    password = os.environ.get("SMTP_PASSWORD")
    from_email = os.environ.get("SMTP_FROM_EMAIL", username)
    port = int(os.environ.get("SMTP_PORT", "587"))

    if not (host and username and password and from_email):
        return False

    message = MIMEText(body)
    message["Subject"] = subject
    message["From"] = from_email
    message["To"] = to_email

    try:
        with smtplib.SMTP(host, port, timeout=REQUEST_TIMEOUT) as server:
            server.starttls()
            server.login(username, password)
            server.sendmail(from_email, [to_email], message.as_string())
        return True
    except Exception:
        return False


def send_sms(to_phone: str, body: str) -> bool:
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_FROM_NUMBER")

    if not (account_sid and auth_token and from_number):
        return False

    try:
        response = requests.post(
            TWILIO_SMS_URL.format(sid=account_sid),
            auth=(account_sid, auth_token),
            data={"From": from_number, "To": to_phone, "Body": body},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return True
    except Exception:
        return False
