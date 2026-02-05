"""Inbox poller that publishes inbound email events to Manager.

Tier 0 ingress: polls a single inbox provider, deduplicates messages, and
emits envelopes to `{tenant}:manager:tasks` so the existing reply chain runs.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
import uuid
from typing import Optional
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=True)
except Exception:
    pass

from services.redis import RedisStreamsClient
from core.envelope import task as create_task_envelope, to_redis_fields
from services.email.providers import (
    InboxProvider,
    GmailApiInboxProvider,
    ImapInboxProvider,
    InboundEmailEvent,
)
from services.email.pre_filter import pre_filter_email, PreFilterResult

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


DEDUP_TTL_SECONDS = int(os.getenv("INBOX_DEDUP_TTL_SECONDS", "86400"))
DEFAULT_POLL_INTERVAL = int(os.getenv("INBOX_POLL_INTERVAL_S", "60"))

# Backpressure: skip poll if manager stream has too many pending messages
MAX_PENDING_MESSAGES = int(os.getenv("INBOX_MAX_PENDING", "100"))
BACKPRESSURE_ENABLED = os.getenv("INBOX_BACKPRESSURE_ENABLED", "1").lower() in ("1", "true", "yes")

# Pre-filter configuration
PRE_FILTER_ENABLED = os.getenv("INBOX_PRE_FILTER_ENABLED", "1").lower() in ("1", "true", "yes")
# Categories to skip entirely (not published to Manager)
PRE_FILTER_SKIP_CATEGORIES = set(
    os.getenv("INBOX_PRE_FILTER_SKIP_CATEGORIES", "bounce,marketing,newsletter").split(",")
)
# Minimum confidence to apply pre-filter skip
PRE_FILTER_SKIP_CONFIDENCE = float(os.getenv("INBOX_PRE_FILTER_SKIP_CONFIDENCE", "0.8"))


def make_dedup_key(tenant_id: str, provider: str, message_id: str) -> str:
    return f"{tenant_id}:inbox:seen:{provider}:{message_id}"


def should_process(redis_client: RedisStreamsClient, key: str) -> bool:
    namespaced = redis_client._chan(key)  # reuse namespace handling
    if redis_client.client.exists(namespaced):
        return False
    redis_client.client.setex(namespaced, DEDUP_TTL_SECONDS, "1")
    return True


def apply_pre_filter(event: InboundEmailEvent) -> PreFilterResult:
    """Apply Tier-0 pre-filter to classify obvious email types."""
    return pre_filter_email(
        from_email=event.from_email,
        subject=event.subject,
        body=event.body,
        list_unsubscribe=event.list_unsubscribe,
        precedence=event.precedence,
        auto_response_suppress=event.auto_response_suppress,
        x_mailer=event.x_mailer,
        from_name=event.from_name,
    )


def check_backpressure(redis_client: RedisStreamsClient, tenant_id: str) -> bool:
    """
    Check if manager stream has too many pending messages.
    
    Returns:
        True if backpressure should be applied (skip this poll cycle)
        False if it's okay to proceed
    """
    if not BACKPRESSURE_ENABLED:
        return False
    
    try:
        stream_key = f"{tenant_id}:manager:tasks"
        namespaced = redis_client._chan(stream_key)
        # XLEN returns number of entries in the stream
        pending = redis_client.client.xlen(namespaced)
        if pending >= MAX_PENDING_MESSAGES:
            logger.warning(
                "Backpressure: %d pending messages (threshold=%d), skipping poll",
                pending,
                MAX_PENDING_MESSAGES,
            )
            return True
        return False
    except Exception as e:
        logger.warning("Backpressure check failed: %s (proceeding with poll)", e)
        return False


def publish_event(
    redis_client: RedisStreamsClient,
    tenant_id: str,
    event: InboundEmailEvent,
    pre_filter_result: PreFilterResult,
) -> None:
    payload = {
        "goal": "process inbound email",
        "context": {
            "email_event": event.to_payload(),
            "actions_allowed": ["store", "enrich", "reply"],
            "pre_filter": {
                "category": pre_filter_result.category,
                "confidence": pre_filter_result.confidence,
                "reason": pre_filter_result.reason,
            },
        },
        "intent": "inbound",
    }
    envelope = create_task_envelope(
        source="inbox_poller",
        task_id=f"inbound_{uuid.uuid4()}",
        payload=payload,
        tenant_id=tenant_id,
    )
    stream = f"{tenant_id}:manager:tasks"
    redis_client.xadd(stream, to_redis_fields(envelope))
    logger.info("Published inbound email to %s (message_id=%s)", stream, event.message_id)


def build_provider(provider_name: str, *, credentials_path: Optional[str], inbox_user: Optional[str]) -> InboxProvider:
    name = provider_name.lower()
    if name == "gmail":
        return GmailApiInboxProvider(credentials_path=credentials_path, user_id=inbox_user)
    if name == "imap":
        host = os.getenv("IMAP_HOST")
        username = os.getenv("IMAP_USERNAME")
        password = os.getenv("IMAP_PASSWORD")
        mailbox = os.getenv("IMAP_MAILBOX", "INBOX")
        if not host or not username or not password:
            raise RuntimeError("IMAP_HOST, IMAP_USERNAME, IMAP_PASSWORD must be set for IMAP provider")
        return ImapInboxProvider(host=host, username=username, password=password, mailbox=mailbox)
    raise RuntimeError(f"Unknown INBOX_PROVIDER: {provider_name}")


def run_poller(
    *,
    tenant_id: str,
    provider: str,
    poll_interval: int,
    credentials_path: Optional[str],
    inbox_user: Optional[str],
    mark_read: bool = True,
    once: bool = False,
) -> None:
    redis_client = RedisStreamsClient()
    inbox_provider = build_provider(provider, credentials_path=credentials_path, inbox_user=inbox_user)

    logger.info(
        "Inbox poller started (tenant=%s, provider=%s, poll_interval=%ss, mark_read=%s)",
        tenant_id,
        inbox_provider.name,
        poll_interval,
        mark_read,
    )

    while True:
        try:
            # Backpressure check: skip poll if manager stream is overloaded
            if check_backpressure(redis_client, tenant_id):
                if once:
                    logger.info("Run-once + backpressure; exiting")
                    break
                time.sleep(poll_interval)
                continue

            events = inbox_provider.fetch_new_messages()
            published = 0
            skipped_prefilter = 0
            for event in events:
                dedup_key = make_dedup_key(tenant_id, inbox_provider.name, event.message_id)
                if not should_process(redis_client, dedup_key):
                    logger.debug("Skipping duplicate: %s", event.message_id)
                    continue

                # Apply Tier-0 pre-filter
                pre_filter_result = apply_pre_filter(event) if PRE_FILTER_ENABLED else PreFilterResult(None, 0.0, "Pre-filter disabled")

                # Skip categories with high confidence (e.g., bounces)
                if (
                    pre_filter_result.category in PRE_FILTER_SKIP_CATEGORIES
                    and pre_filter_result.confidence >= PRE_FILTER_SKIP_CONFIDENCE
                ):
                    logger.info(
                        "Pre-filter SKIP: %s (category=%s, confidence=%.2f, reason=%s)",
                        event.message_id,
                        pre_filter_result.category,
                        pre_filter_result.confidence,
                        pre_filter_result.reason,
                    )
                    skipped_prefilter += 1
                    # Still mark as read so we don't re-process
                    if mark_read:
                        try:
                            inbox_provider.mark_as_read(event)
                        except Exception as mark_err:
                            logger.warning("Failed to mark skipped message as read: %s", mark_err)
                    continue

                # Store pre-filter category on event for downstream use
                event.pre_filter_category = pre_filter_result.category

                publish_event(redis_client, tenant_id, event, pre_filter_result)
                published += 1
                # Mark as read after successful publish to avoid reprocessing
                if mark_read:
                    try:
                        inbox_provider.mark_as_read(event)
                    except Exception as mark_err:
                        logger.warning("Failed to mark message as read: %s", mark_err)
            logger.info("Poll complete: scanned=%d published=%d skipped_prefilter=%d", len(events), published, skipped_prefilter)
            if once:
                logger.info("Run-once enabled; exiting after single poll")
                break
        except KeyboardInterrupt:
            logger.info("Inbox poller interrupted; exiting")
            break
        except Exception as exc:  # pragma: no cover - operational logging
            logger.error("Inbox poller error: %s", exc, exc_info=True)
            if once:
                logger.info("Run-once enabled; exiting after error")
                break

        if not once:
            time.sleep(poll_interval)


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Inbox poller -> Manager tasks")
    parser.add_argument("--tenant", dest="tenant_id", default=os.getenv("TENANT_ID", "agentic-dev"))
    parser.add_argument("--provider", dest="provider", default=os.getenv("INBOX_PROVIDER", "gmail"))
    parser.add_argument(
        "--poll-interval",
        dest="poll_interval",
        type=int,
        default=DEFAULT_POLL_INTERVAL,
        help="Polling interval in seconds",
    )
    parser.add_argument(
        "--credentials-path",
        dest="credentials_path",
        default=os.getenv("GMAIL_READ_CREDENTIALS_PATH"),
        help="Path to Gmail API credentials (if using Gmail provider)",
    )
    parser.add_argument(
        "--inbox-user",
        dest="inbox_user",
        default=os.getenv("GMAIL_INBOX_USER") or os.getenv("GMAIL_SENDER_EMAIL"),
        help="Gmail userId or email for inbox access",
    )
    parser.add_argument(
        "--no-mark-read",
        dest="mark_read",
        action="store_false",
        default=True,
        help="Do not mark messages as read after processing",
    )
    parser.add_argument(
        "--once",
        dest="once",
        action="store_true",
        default=bool(int(os.getenv("INBOX_POLL_ONCE", "0"))),
        help="Run a single poll cycle then exit (or set INBOX_POLL_ONCE=1)",
    )
    args = parser.parse_args(argv)

    run_poller(
        tenant_id=args.tenant_id,
        provider=args.provider,
        poll_interval=args.poll_interval,
        credentials_path=args.credentials_path,
        inbox_user=args.inbox_user,
        mark_read=args.mark_read,
        once=args.once,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
