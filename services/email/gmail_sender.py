"""Gmail SMTP sender.

Uses an app password to send emails via smtp.gmail.com:587 with STARTTLS.

Supports:
- Plain-text body (required)
- Optional HTML alternative (multipart/alternative)
- Optional file attachments
- DRY_RUN mode for testing (set EMAIL_DRY_RUN=1)
"""
from __future__ import annotations

import logging
import mimetypes
import os
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import make_msgid
from pathlib import Path
from typing import Optional, Sequence, Union

logger = logging.getLogger(__name__)

# DRY_RUN mode: log instead of sending (useful for dev/test)
DRY_RUN = os.getenv("EMAIL_DRY_RUN", "0").lower() in ("1", "true", "yes")


class GmailConfigError(RuntimeError):
    """Raised when required Gmail config is missing."""


@dataclass(frozen=True)
class EmailAttachment:
    """Attachment data for send_email_via_gmail."""

    filename: str
    content: bytes
    mime_type: str = "application/octet-stream"


def _guess_mime_type(filename: str) -> str:
    mt, _ = mimetypes.guess_type(filename)
    return mt or "application/octet-stream"


def _load_attachment(path: Union[str, Path]) -> EmailAttachment:
    p = Path(path)
    content = p.read_bytes()
    mime_type = _guess_mime_type(p.name)
    return EmailAttachment(filename=p.name, content=content, mime_type=mime_type)


def send_email_via_gmail(
    *,
    to_email: str,
    subject: str,
    body: str,
    html_body: Optional[str] = None,
    attachments: Optional[Sequence[Union[EmailAttachment, str, Path]]] = None,
    from_email: Optional[str] = None,
    app_password: Optional[str] = None,
    reply_to: Optional[str] = None,
    smtp_host: str = "smtp.gmail.com",
    smtp_port: int = 587,
) -> str:
    """Send an email via Gmail SMTP.

    Args:
        to_email: Recipient address.
        subject: Email subject.
        body: Plain-text body (required).
        html_body: Optional HTML body (sent as alternative).
        attachments: Optional list of EmailAttachment objects or file paths.
        from_email: Sender address (defaults to GMAIL_SENDER_EMAIL env var).
        app_password: Gmail app password (defaults to GMAIL_APP_PASSWORD env var).
        reply_to: Optional Reply-To address.
        smtp_host: SMTP server (default smtp.gmail.com).
        smtp_port: SMTP port (default 587 for STARTTLS).

    Returns:
        The generated Message-ID string on success.

    Raises:
        GmailConfigError: If sender email or app password is not configured.
        smtplib.SMTPException: On send failure.
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

    # Plain-text is always set first
    msg.set_content(body)

    # Optional HTML alternative
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    # Optional attachments
    if attachments:
        for item in attachments:
            att = item
            if isinstance(item, (str, Path)):
                att = _load_attachment(item)
            if not isinstance(att, EmailAttachment):
                raise TypeError(f"Unsupported attachment type: {type(item)}")

            maintype, subtype = (
                att.mime_type.split("/", 1) if "/" in att.mime_type else ("application", "octet-stream")
            )
            msg.add_attachment(att.content, maintype=maintype, subtype=subtype, filename=att.filename)

    # DRY_RUN: log email details instead of sending
    if DRY_RUN:
        logger.info(
            "[DRY_RUN] Would send email: to=%s, subject=%s, message_id=%s, body_preview=%s",
            to_email,
            subject,
            message_id,
            body[:100] + "..." if len(body) > 100 else body,
        )
        return message_id

    context = ssl.create_default_context()
    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls(context=context)
        server.login(sender, password)
        server.send_message(msg)

    return message_id
