"""Inbox provider abstractions and normalized inbound email event model.

Providers implement `fetch_new_messages()` and return normalized events.
GmailApiInboxProvider uses the Gmail API (OAuth); ImapInboxProvider uses IMAP.
"""
from __future__ import annotations

import imaplib
import logging
import os
from dataclasses import asdict, dataclass
from email import message_from_bytes
from email.header import decode_header
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class InboundEmailEvent:
    """Normalized inbound email payload expected by Manager/Leads."""

    provider: str
    message_id: str
    thread_id: Optional[str]
    subject: Optional[str]
    body: Optional[str]
    from_email: str
    to_email: str
    received_at: Optional[str]
    from_name: Optional[str] = None
    # Internal ID for mark-as-read (e.g., Gmail message ID or IMAP UID)
    internal_id: Optional[str] = None

    # Header metadata for classification (extracted from raw email)
    list_unsubscribe: Optional[str] = None  # List-Unsubscribe header (newsletter indicator)
    precedence: Optional[str] = None  # Precedence: bulk/list/junk
    auto_response_suppress: Optional[str] = None  # X-Auto-Response-Suppress (OOO/auto-reply)
    x_mailer: Optional[str] = None  # X-Mailer (system-generated email detection)
    reply_to: Optional[str] = None  # Reply-To header
    # Pre-filter result (set by Tier-0 if obvious junk)
    pre_filter_category: Optional[str] = None  # bounce, unsubscribe, system, newsletter, or None

    def to_payload(self) -> dict:
        d = asdict(self)
        # internal_id is not sent downstream; used only for mark-as-read
        d.pop("internal_id", None)

        # Canonical keys used by Leads/Persistence inbound flow
        # (keep from_email/to_email for debugging/compat).
        d["from"] = d.get("from_email")
        d["to"] = d.get("to_email")
        d["body"] = d.get("body")

        # Include header metadata for classification (downstream can use these)
        d["headers"] = {
            "list_unsubscribe": d.pop("list_unsubscribe", None),
            "precedence": d.pop("precedence", None),
            "auto_response_suppress": d.pop("auto_response_suppress", None),
            "x_mailer": d.pop("x_mailer", None),
            "reply_to": d.pop("reply_to", None),
        }
        return d


class InboxProvider:
    """Base interface for inbox providers."""

    name: str = "unknown"

    def fetch_new_messages(self) -> List[InboundEmailEvent]:
        raise NotImplementedError

    def mark_as_read(self, event: InboundEmailEvent) -> None:
        """Mark message as read (optional; default no-op)."""
        pass


# ---------------------------------------------------------------------------
# Gmail API Provider
# ---------------------------------------------------------------------------


class GmailApiInboxProvider(InboxProvider):
    """Gmail API provider using OAuth2.

    Requires:
    - credentials_path: Path to OAuth client secrets JSON from Google Cloud Console.
    - token_path: Where to store/load the access token (default: gmail_token.json).
    - user_id: Gmail userId, typically "me".

    On first run, opens a browser for OAuth consent.
    """

    name = "gmail"

    def __init__(
        self,
        *,
        credentials_path: Optional[str] = None,
        token_path: Optional[str] = None,
        user_id: Optional[str] = None,
        max_results: int = 20,
    ):
        self.credentials_path = credentials_path or os.getenv("GMAIL_READ_CREDENTIALS_PATH")
        self.token_path = token_path or os.getenv("GMAIL_TOKEN_PATH", "gmail_token.json")
        self.user_id = user_id or "me"
        self.max_results = max_results
        self._reader = None

    def _get_reader(self):
        if self._reader is not None:
            return self._reader

        if not self.credentials_path:
            raise RuntimeError(
                "GmailApiInboxProvider requires GMAIL_READ_CREDENTIALS_PATH env var or credentials_path arg"
            )

        from services.email.gmail_reader import GmailReader, GmailReaderConfig

        cfg = GmailReaderConfig(
            credentials_json_path=self.credentials_path,
            token_json_path=self.token_path,
            allow_modify=True,
        )
        self._reader = GmailReader(cfg)
        return self._reader

    def fetch_new_messages(self) -> List[InboundEmailEvent]:
        reader = self._get_reader()
        # Default behavior is conservative: only process unread mail.
        # You can override this (e.g., to include read mail) using a Gmail search query.
        # Examples:
        # - newer_than:2h -in:spam -in:trash
        # - from:someone@example.com newer_than:7d
        inbox_query = os.getenv("GMAIL_INBOX_QUERY", "is:unread").strip() or "is:unread"
        ids = reader.list_message_ids(user_id=self.user_id, query=inbox_query, max_results=self.max_results)
        logger.info("Gmail: found %d message(s) for query=%r", len(ids), inbox_query)

        events: List[InboundEmailEvent] = []
        for gmail_id in ids:
            try:
                raw_msg = reader.get_message_raw(message_id=gmail_id, user_id=self.user_id)
                parsed = reader.parse_raw_message(raw_msg)
                events.append(
                    InboundEmailEvent(
                        provider="gmail",
                        message_id=parsed["message_id"],
                        thread_id=parsed["thread_id"],
                        subject=parsed["subject"],
                        body=parsed["body_text"],
                        from_email=parsed["from_email"],
                        to_email=parsed["to_email"],
                        received_at=parsed["received_at"],
                        from_name=parsed["from_name"],
                        internal_id=gmail_id,
                        # Header metadata for classification
                        list_unsubscribe=parsed.get("list_unsubscribe"),
                        precedence=parsed.get("precedence"),
                        auto_response_suppress=parsed.get("auto_response_suppress"),
                        x_mailer=parsed.get("x_mailer"),
                        reply_to=parsed.get("reply_to"),
                    )
                )
            except Exception as e:
                logger.error("Gmail: failed to fetch/parse message %s: %s", gmail_id, e)
        return events

    def mark_as_read(self, event: InboundEmailEvent) -> None:
        if not event.internal_id:
            return
        reader = self._get_reader()
        reader.mark_as_read(message_id=event.internal_id, user_id=self.user_id)


# ---------------------------------------------------------------------------
# IMAP Provider
# ---------------------------------------------------------------------------


def _decode_mime_header(raw: str) -> str:
    if not raw:
        return ""
    parts = decode_header(raw)
    decoded = []
    for data, charset in parts:
        if isinstance(data, bytes):
            decoded.append(data.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(str(data))
    return "".join(decoded)


class ImapInboxProvider(InboxProvider):
    """IMAP provider for reading inbox via IMAP4.

    Env vars (if not passed directly):
    - IMAP_HOST, IMAP_USERNAME, IMAP_PASSWORD, IMAP_MAILBOX (default INBOX)
    """

    name = "imap"

    def __init__(
        self,
        *,
        host: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        mailbox: str = "INBOX",
        ssl: bool = True,
        max_results: int = 20,
    ):
        self.host = host or os.getenv("IMAP_HOST")
        self.username = username or os.getenv("IMAP_USERNAME")
        self.password = password or os.getenv("IMAP_PASSWORD")
        self.mailbox = mailbox or os.getenv("IMAP_MAILBOX", "INBOX")
        self.ssl = ssl
        self.max_results = max_results

    def _connect(self):
        if not self.host or not self.username or not self.password:
            raise RuntimeError("IMAP_HOST, IMAP_USERNAME, IMAP_PASSWORD must be set")
        if self.ssl:
            conn = imaplib.IMAP4_SSL(self.host)
        else:
            conn = imaplib.IMAP4(self.host)
        conn.login(self.username, self.password)
        return conn

    def fetch_new_messages(self) -> List[InboundEmailEvent]:
        conn = self._connect()
        try:
            conn.select(self.mailbox, readonly=False)
            status, data = conn.search(None, "UNSEEN")
            if status != "OK":
                logger.warning("IMAP search failed: %s", status)
                return []

            uids = data[0].split() if data[0] else []
            uids = uids[: self.max_results]
            logger.info("IMAP: found %d unread message(s)", len(uids))

            events: List[InboundEmailEvent] = []
            for uid in uids:
                try:
                    status, msg_data = conn.fetch(uid, "(RFC822)")
                    if status != "OK" or not msg_data or not msg_data[0]:
                        continue
                    raw_email = msg_data[0][1]
                    eml = message_from_bytes(raw_email)

                    def hdr(name: str) -> str:
                        return _decode_mime_header(str(eml.get(name, "")).strip())

                    from_header = hdr("From")
                    from_name, from_email = parseaddr(from_header)
                    from_name = _decode_mime_header(from_name) if from_name else None

                    received_at = None
                    date_str = hdr("Date")
                    if date_str:
                        try:
                            received_at = parsedate_to_datetime(date_str).isoformat()
                        except Exception:
                            pass

                    # Extract plain-text body
                    body_text = ""
                    if eml.is_multipart():
                        for part in eml.walk():
                            ctype = part.get_content_type()
                            disp = (part.get("Content-Disposition") or "").lower()
                            if ctype == "text/plain" and "attachment" not in disp:
                                payload = part.get_payload(decode=True) or b""
                                body_text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
                                break
                    else:
                        payload = eml.get_payload(decode=True) or b""
                        body_text = payload.decode(eml.get_content_charset() or "utf-8", errors="replace")

                    events.append(
                        InboundEmailEvent(
                            provider="imap",
                            message_id=hdr("Message-ID") or uid.decode(),
                            thread_id=hdr("In-Reply-To") or hdr("References") or None,
                            subject=hdr("Subject"),
                            body=body_text.strip(),
                            from_email=from_email,
                            to_email=hdr("To"),
                            received_at=received_at,
                            from_name=from_name,
                            internal_id=uid.decode(),
                        )
                    )
                except Exception as e:
                    logger.error("IMAP: failed to fetch/parse UID %s: %s", uid, e)
            return events
        finally:
            try:
                conn.close()
                conn.logout()
            except Exception:
                pass

    def mark_as_read(self, event: InboundEmailEvent) -> None:
        if not event.internal_id:
            return
        conn = self._connect()
        try:
            conn.select(self.mailbox, readonly=False)
            conn.store(event.internal_id.encode(), "+FLAGS", "\\Seen")
        finally:
            try:
                conn.close()
                conn.logout()
            except Exception:
                pass
