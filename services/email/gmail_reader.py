"""Gmail API reader for inbox monitoring.

Provides OAuth2 authentication and methods to:
- List unread messages
- Fetch message content (raw RFC822)
- Parse into normalized InboundEmailEvent
- Mark messages as read

Requires credentials JSON from Google Cloud Console (OAuth 2.0 Client ID).
On first run, opens a browser for user consent; stores token.json for reuse.
"""
from __future__ import annotations

import base64
import logging
import os
import re
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse
from dataclasses import dataclass
from email import message_from_bytes
from email.header import decode_header
from email.message import Message
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Lazy imports to avoid hard failures if google libs not installed
_google_libs_available = False
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    _google_libs_available = True
except ImportError:
    pass


class GmailReaderConfigError(RuntimeError):
    """Raised when Gmail reader configuration is missing or invalid."""


SCOPES_READONLY = ["https://www.googleapis.com/auth/gmail.readonly"]
SCOPES_MODIFY = ["https://www.googleapis.com/auth/gmail.modify"]


@dataclass
class GmailReaderConfig:
    """Configuration for GmailReader.

    Attributes:
        credentials_json_path: Path to OAuth client secrets JSON from Google Cloud Console.
        token_json_path: Path where access/refresh token will be stored.
        allow_modify: If True, uses gmail.modify scope (enables mark-as-read).
    """

    credentials_json_path: str
    token_json_path: str = "gmail_token.json"
    allow_modify: bool = True


def _decode_mime_header(raw: str) -> str:
    """Decode MIME-encoded header (e.g., =?utf-8?B?...?=)."""
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


def _extract_email(from_header: str) -> tuple[str, str]:
    """Extract (name, email) from a From header."""
    name, email = parseaddr(from_header)
    name = _decode_mime_header(name) if name else None
    return name or "", email or ""


class GmailReader:
    """Gmail API client for reading inbox messages."""

    def __init__(self, cfg: GmailReaderConfig):
        if not _google_libs_available:
            raise ImportError(
                "Gmail API dependencies not installed. Run: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
            )
        self.cfg = cfg
        self._service = None

    def _get_service(self):
        """Authenticate and build Gmail API service (cached)."""
        if self._service is not None:
            return self._service

        creds: Optional[Credentials] = None
        token_path = Path(self.cfg.token_json_path)
        scopes = SCOPES_MODIFY if self.cfg.allow_modify else SCOPES_READONLY

        # Load existing token
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), scopes=scopes)

        # Refresh or get new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("Refreshing expired Gmail credentials")
                creds.refresh(Request())
            else:
                creds_path = Path(self.cfg.credentials_json_path)
                if not creds_path.exists():
                    raise GmailReaderConfigError(
                        f"Missing Gmail OAuth credentials JSON at: {self.cfg.credentials_json_path}. "
                        "Download from Google Cloud Console > APIs & Services > Credentials."
                    )
                logger.info("Starting OAuth flow for Gmail API (browser will open)")
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), scopes=scopes)
                except json.JSONDecodeError as e:
                    raise GmailReaderConfigError(
                        f"Invalid Gmail OAuth credentials JSON at: {self.cfg.credentials_json_path}. "
                        "The file is empty or not valid JSON. Replace it with the OAuth client secrets JSON "
                        "downloaded from Google Cloud Console."
                    ) from e

                oauth_mode = os.getenv("GMAIL_OAUTH_FLOW", "local_server").lower().strip()
                if oauth_mode in ("console", "headless"):
                    # Some google-auth-oauthlib versions don't provide run_console().
                    # In container/headless environments, use a local server callback that the host can reach.
                    bind_host = os.getenv("GMAIL_OAUTH_HOST", "0.0.0.0").strip() or "0.0.0.0"
                    public_host = os.getenv("GMAIL_OAUTH_PUBLIC_HOST", "localhost").strip() or "localhost"
                    port_str = os.getenv("GMAIL_OAUTH_PORT", "8080").strip() or "8080"
                    try:
                        port = int(port_str)
                    except ValueError:
                        port = 8080

                    # If run_console exists, it is typically interactive (stdin). Prefer headless HTTP callback.
                    # We implement our own minimal callback server so we can bind to 0.0.0.0 inside the container
                    # while using a browser-friendly redirect URI (http://localhost:<port>/) on the host.
                    flow.redirect_uri = f"http://{public_host}:{port}/"

                    auth_url, _ = flow.authorization_url(
                        access_type="offline",
                        include_granted_scopes="true",
                        prompt="consent",
                    )
                    logger.info(
                        "Starting Gmail OAuth headless callback server on %s:%s (redirect_uri=%s)",
                        bind_host,
                        port,
                        flow.redirect_uri,
                    )
                    logger.info("Please visit this URL to authorize this application: %s", auth_url)

                    code_holder: dict[str, str] = {}
                    done = threading.Event()

                    class _OAuthHandler(BaseHTTPRequestHandler):
                        def do_GET(self):  # noqa: N802
                            try:
                                parsed = urlparse(self.path)
                                qs = parse_qs(parsed.query)
                                code = (qs.get("code") or [""])[0]
                                error = (qs.get("error") or [""])[0]
                                if error:
                                    code_holder["error"] = error
                                if code:
                                    code_holder["code"] = code
                            finally:
                                self.send_response(200)
                                self.send_header("Content-Type", "text/plain; charset=utf-8")
                                self.end_headers()
                                if "code" in code_holder:
                                    self.wfile.write(b"OAuth received. You can close this tab.")
                                elif "error" in code_holder:
                                    self.wfile.write(b"OAuth error received. Check logs.")
                                else:
                                    self.wfile.write(b"No OAuth code found. Check URL/query string.")
                                done.set()

                        def log_message(self, format, *args):  # noqa: A002
                            # Silence noisy HTTPServer logging.
                            return

                    httpd = HTTPServer((bind_host, port), _OAuthHandler)
                    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
                    server_thread.start()

                    timeout_s = float(os.getenv("GMAIL_OAUTH_TIMEOUT_S", "300").strip() or "300")
                    start = time.time()
                    while not done.is_set() and (time.time() - start) < timeout_s:
                        time.sleep(0.2)

                    httpd.shutdown()
                    httpd.server_close()

                    if "error" in code_holder:
                        raise GmailReaderConfigError(f"OAuth authorization failed: {code_holder['error']}")
                    if "code" not in code_holder:
                        raise GmailReaderConfigError(
                            "OAuth authorization timed out waiting for callback. "
                            f"Open the logged URL in a browser and ensure http://{public_host}:{port}/ is reachable."
                        )

                    flow.fetch_token(code=code_holder["code"])
                    creds = flow.credentials
                else:
                    # Standard local machine flow.
                    creds = flow.run_local_server(port=0)

            # Save token for future runs
            token_path.write_text(creds.to_json(), encoding="utf-8")
            logger.info("Gmail token saved to %s", token_path)

        self._service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        return self._service

    def list_message_ids(
        self,
        *,
        user_id: str = "me",
        query: str = "is:unread",
        max_results: int = 20,
    ) -> List[str]:
        """List message IDs matching query (default: unread messages).

        Args:
            user_id: Gmail user ID ("me" for authenticated user).
            query: Gmail search query (e.g., "is:unread", "from:someone@example.com").
            max_results: Maximum number of message IDs to return.

        Returns:
            List of Gmail message IDs.
        """
        svc = self._get_service()
        resp = svc.users().messages().list(userId=user_id, q=query, maxResults=max_results).execute()
        msgs = resp.get("messages", []) or []
        return [m["id"] for m in msgs if "id" in m]

    def get_message_raw(self, *, message_id: str, user_id: str = "me") -> Dict[str, Any]:
        """Fetch full message in raw format.

        Returns dict with keys: id, threadId, labelIds, raw (base64-encoded RFC822).
        """
        svc = self._get_service()
        return svc.users().messages().get(userId=user_id, id=message_id, format="raw").execute()

    def mark_as_read(self, *, message_id: str, user_id: str = "me") -> None:
        """Remove UNREAD label from message (requires gmail.modify scope)."""
        if not self.cfg.allow_modify:
            logger.debug("mark_as_read skipped: allow_modify=False")
            return
        svc = self._get_service()
        svc.users().messages().modify(
            userId=user_id,
            id=message_id,
            body={"removeLabelIds": ["UNREAD"]},
        ).execute()
        logger.debug("Marked message %s as read", message_id)

    @staticmethod
    def parse_raw_message(gmail_raw_obj: Dict[str, Any], to_email: str = "") -> Dict[str, Any]:
        """Parse raw Gmail message into normalized dict.

        Args:
            gmail_raw_obj: Response from get_message_raw().
            to_email: Fallback To address if not in headers.

        Returns:
            Dict with keys: provider, message_id, thread_id, subject, from_email,
            from_name, to_email, body_text, received_at, gmail_id, labels.
        """
        raw = gmail_raw_obj.get("raw")
        if not raw:
            raise ValueError("Gmail message missing 'raw' content")

        msg_bytes = base64.urlsafe_b64decode(raw.encode("utf-8"))
        eml: Message = message_from_bytes(msg_bytes)

        def hdr(name: str) -> str:
            return _decode_mime_header(str(eml.get(name, "")).strip())

        from_name, from_email = _extract_email(hdr("From"))

        # Parse received date
        received_at = None
        date_str = hdr("Date")
        if date_str:
            try:
                received_at = parsedate_to_datetime(date_str).isoformat()
            except Exception:
                pass

        # Body extraction: prefer plain-text
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

        return {
            "provider": "gmail",
            "message_id": hdr("Message-ID") or gmail_raw_obj.get("id"),
            "thread_id": gmail_raw_obj.get("threadId"),
            "subject": hdr("Subject"),
            "from_email": from_email,
            "from_name": from_name or None,
            "to_email": hdr("To") or to_email,
            "body_text": body_text.strip(),
            "received_at": received_at,
            "gmail_id": gmail_raw_obj.get("id"),
            "labels": gmail_raw_obj.get("labelIds", []),
            # Header metadata for classification
            "list_unsubscribe": hdr("List-Unsubscribe") or None,
            "precedence": hdr("Precedence") or None,
            "auto_response_suppress": hdr("X-Auto-Response-Suppress") or None,
            "x_mailer": hdr("X-Mailer") or None,
            "reply_to": hdr("Reply-To") or None,
        }
