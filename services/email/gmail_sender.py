"""Gmail SMTP sender.

Uses an app password to send plain-text emails via smtp.gmail.com:587 with STARTTLS.
"""
from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import make_msgid
from typing import Optional


class GmailConfigError(RuntimeError):
    """Raised when required Gmail config is missing."""


def send_email_via_gmail(
    *,
    to_email: str,
    subject: str,
    body: str,
    from_email: Optional[str] = None,
    app_password: Optional[str] = None,
    reply_to: Optional[str] = None,
    smtp_host: str = "smtp.gmail.com",
    smtp_port: int = 587,
) -> str:
    """Send a plain-text email via Gmail SMTP.

    Returns the Message-ID string on success.
    Raises GmailConfigError on missing credentials and smtplib.SMTPException on send failure.
    """
    sender = from_email or os.getenv("GMAIL_SENDER_EMAIL")
    password = app_password or os.getenv("GMAIL_APP_PASSWORD")

    if not sender or not password:
        raise GmailConfigError("Gmail sender email or app password not configured")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_email
    if reply_to:
        msg["Reply-To"] = reply_to
    message_id = make_msgid(domain=sender.split("@")[-1])
    msg["Message-ID"] = message_id
    msg.set_content(body)

    context = ssl.create_default_context()
    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls(context=context)
        server.login(sender, password)
        server.send_message(msg)

    return message_id
