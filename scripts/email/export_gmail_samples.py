"""Export a redacted sample set of Gmail messages for debugging pre-filter/classifier.

This script is meant for safely sharing examples without leaking sensitive content.
It pulls messages via Gmail API using the existing GmailReader, then writes a JSONL
file with:
- subject
- key headers (List-Unsubscribe, Precedence, etc.)
- short, redacted body preview

Usage (PowerShell):
  & ".\.venv\Scripts\python.exe" -m scripts.email.export_gmail_samples --query "newer_than:7d" --limit 50

Notes:
- Requires OAuth to already be completed by the inbox poller (token saved).
- Reads paths from env: GMAIL_READ_CREDENTIALS_PATH, GMAIL_TOKEN_PATH.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.email.gmail_reader import GmailReader, GmailReaderConfig


_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _redact_emails(text: str) -> str:
    return _EMAIL_RE.sub("<redacted@email>", text or "")


def _truncate(text: str, n: int) -> str:
    text = text or ""
    return text if len(text) <= n else text[:n] + "…"


def _normalize_sample(parsed: Dict[str, Any], *, body_limit: int) -> Dict[str, Any]:
    return {
        "provider": parsed.get("provider"),
        "received_at": parsed.get("received_at"),
        "subject": _truncate(_redact_emails(parsed.get("subject") or ""), 200),
        "from_name": _truncate(parsed.get("from_name") or "", 120),
        # Do not include raw email addresses
        "from_email": "<redacted@email>" if (parsed.get("from_email") or "") else "",
        "to_email": "<redacted@email>" if (parsed.get("to_email") or "") else "",
        "message_id": _truncate(parsed.get("message_id") or "", 200),
        "thread_id": parsed.get("thread_id"),
        "labels": parsed.get("labels") or [],
        "headers": {
            "list_unsubscribe": _truncate(parsed.get("list_unsubscribe") or "", 300),
            "precedence": _truncate(parsed.get("precedence") or "", 120),
            "auto_response_suppress": _truncate(parsed.get("auto_response_suppress") or "", 120),
            "x_mailer": _truncate(parsed.get("x_mailer") or "", 120),
            "reply_to": _truncate(_redact_emails(parsed.get("reply_to") or ""), 200),
        },
        "body_preview": _truncate(_redact_emails(parsed.get("body_text") or ""), body_limit),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export redacted Gmail message samples to JSONL")
    parser.add_argument("--query", default=os.getenv("GMAIL_EXPORT_QUERY", "newer_than:7d"))
    parser.add_argument("--limit", type=int, default=int(os.getenv("GMAIL_EXPORT_LIMIT", "50")))
    parser.add_argument("--body-limit", type=int, default=int(os.getenv("GMAIL_EXPORT_BODY_LIMIT", "800")))
    parser.add_argument(
        "--out",
        default=os.getenv("GMAIL_EXPORT_OUT", "artifacts/gmail_samples.jsonl"),
        help="Output JSONL path (workspace-relative or absolute).",
    )

    args = parser.parse_args()

    creds_path = os.getenv("GMAIL_READ_CREDENTIALS_PATH", "/data/gmail/credentials.json")
    token_path = os.getenv("GMAIL_TOKEN_PATH", "/data/gmail/gmail_token.json")
    inbox_user = os.getenv("GMAIL_INBOX_USER", "me")

    reader = GmailReader(GmailReaderConfig(credentials_json_path=creds_path, token_json_path=token_path, allow_modify=False))

    # Use the Gmail API search query directly.
    ids = reader.list_message_ids(user_id=inbox_user, query=args.query, max_results=args.limit)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    exported = 0
    with out_path.open("w", encoding="utf-8") as f:
        for message_id in ids:
            raw_obj = reader.get_message_raw(message_id=message_id, user_id=inbox_user)
            parsed = reader.parse_raw_message(raw_obj)
            sample = _normalize_sample(parsed, body_limit=args.body_limit)
            sample["exported_at"] = datetime.utcnow().isoformat() + "Z"
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")
            exported += 1

    print(f"Exported {exported} messages to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
