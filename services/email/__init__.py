"""Email utilities: sending (SMTP), reading (Gmail API / IMAP), and inbox polling."""

from services.email.gmail_sender import send_email_via_gmail, GmailConfigError, EmailAttachment
from services.email.providers import InboundEmailEvent, InboxProvider, GmailApiInboxProvider, ImapInboxProvider

__all__ = [
    # Sending
    "send_email_via_gmail",
    "GmailConfigError",
    "EmailAttachment",
    # Reading / inbox
    "InboundEmailEvent",
    "InboxProvider",
    "GmailApiInboxProvider",
    "ImapInboxProvider",
]
