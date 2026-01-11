"""DLQ Requeue Helper

Re-enqueue messages from DLQ streams back to their task streams.

Supports:
- rag DLQ → rag:tasks
- persist DLQ → persist:tasks

Options:
  --stream rag|persist|both    Which DLQ(s) to process (default: persist)
  --limit N                    Max messages to requeue from each DLQ (default: 10)
  --dry-run                    Print what would be requeued without writing
  --delete                     XDEL DLQ entries after requeue
  --transform-upsert           For persist tasks, rewrite op to upsert with on_conflict=email (to avoid duplicates)
  --filter TEXT                Only requeue DLQ entries whose error contains TEXT (case-insensitive)

Usage (PowerShell):
  # Requeue up to 5 persist DLQ entries as upserts, deleting DLQ entries after
  python scripts/dlq_requeue.py --stream persist --limit 5 --transform-upsert --delete

  # Dry run, show what would be requeued from rag DLQ
  python scripts/dlq_requeue.py --stream rag --limit 3 --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, Optional, Tuple
from pathlib import Path

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.redis import RedisStreamsClient as RedisPubSub
from agent.tools.redis import config as rconf
from agent.utils.typed_envelope import from_redis_message, to_redis_fields, Status


def _parse_dlq_entry(fields: Dict[str, Any]) -> Tuple[Any, Optional[str]]:
    """Extract envelope from DLQ entry.
    
    Returns (envelope, error_str)
    """
    try:
        envelope = from_redis_message(fields)
        error_msg = envelope.error or ""
        return envelope, error_msg
    except Exception as e:
        # Fallback: legacy format with {"task": {...}, "error": ...}
        payload = fields.get("data")
        if isinstance(payload, str):
            try:
                obj = json.loads(payload)
            except Exception:
                return None, None
        elif isinstance(payload, dict):
            obj = payload
        else:
            return None, None

        err = obj.get("error") if isinstance(obj, dict) else None
        if err is not None and not isinstance(err, str):
            try:
                err = json.dumps(err)
            except Exception:
                err = str(err)
        return obj, err


def _maybe_transform_persist_task(envelope: Any, upsert: bool) -> Any:
    """Transform persist task envelope to upsert if requested."""
    if not upsert:
        return envelope
    
    # Check if it's an envelope
    if hasattr(envelope, 'payload') and isinstance(envelope.payload, dict):
        envelope.payload["op"] = "upsert"
        envelope.payload.setdefault("on_conflict", ["email"])
        envelope.status = Status.PENDING  # Reset to pending
        envelope.metadata.retry_count = 0  # Reset retry count
        return envelope
    
    # Legacy fallback: dict payload
    if isinstance(envelope, dict):
        out = dict(envelope)
        out["op"] = "upsert"
        out.setdefault("on_conflict", ["email"])
        return out
    
    return envelope


def requeue(
    which: str,
    limit: int,
    dry_run: bool,
    delete: bool,
    transform_upsert: bool,
    err_filter: Optional[str],
) -> None:
    r = RedisPubSub()
    client = r.client
    err_filter_lower = err_filter.lower() if err_filter else None

    targets = []
    if which in ("rag", "both"):
        targets.append((rconf.full_key(getattr(rconf, "STREAM_DLQ", "rag:dlq")), rconf.STREAM_TASKS, "rag"))
    if which in ("persist", "both"):
        targets.append((rconf.full_key(getattr(rconf, "STREAM_DLQ_WRITE", "persist:dlq")), rconf.STREAM_TASKS_WRITE, "persist"))

    for dlq_key, dest_stream_short, domain in targets:
        dest_stream = dest_stream_short
        print(f"\nDLQ => {dlq_key} | requeue to: {rconf.full_key(dest_stream)}")
        # Fetch oldest first up to limit
        try:
            entries = client.xrange(dlq_key, count=limit)
        except Exception as e:
            print(f"  error: cannot XRANGE {dlq_key}: {e}")
            continue
        if not entries:
            print("  no entries")
            continue

        requeued = 0
        for mid, fields in entries:
            envelope_or_task, err = _parse_dlq_entry(fields)
            if envelope_or_task is None:
                print(f"  skip {mid}: malformed DLQ payload")
                continue
            if err_filter_lower and (not err or err_filter_lower not in err.lower()):
                print(f"  skip {mid}: error does not match filter")
                continue

            to_send = envelope_or_task
            if domain == "persist":
                to_send = _maybe_transform_persist_task(envelope_or_task, transform_upsert)

            print(f"  requeue id={mid} → stream={dest_stream} dry_run={dry_run}")
            if dry_run:
                continue

            try:
                # If it's an envelope, use to_redis_fields; otherwise fallback to legacy JSON
                if hasattr(to_send, 'metadata'):
                    r.xadd(dest_stream, to_redis_fields(to_send), maxlen=rconf.STREAM_MAXLEN)
                else:
                    r.xadd(dest_stream, {"data": json.dumps(to_send)}, maxlen=rconf.STREAM_MAXLEN)
                requeued += 1
            except Exception as e:
                print(f"    xadd error: {e}")
                continue

            if delete:
                try:
                    client.xdel(dlq_key, mid)
                except Exception as e:
                    print(f"    xdel error: {e}")

        print(f"  requeued: {requeued}/{len(entries)}")

    r.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stream", choices=["rag", "persist", "both"], default="persist")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--delete", action="store_true")
    ap.add_argument("--transform-upsert", action="store_true", help="For persist DLQ, rewrite task to upsert with on_conflict=email")
    ap.add_argument("--filter", dest="err_filter", default=None, help="Only requeue DLQs whose error contains this text")
    args = ap.parse_args()

    print("Using REDIS_URL:", os.getenv("REDIS_URL", "(default / local)"))
    print("Namespace:", rconf.NAMESPACE)
    requeue(
        which=args.stream,
        limit=max(1, args.limit),
        dry_run=args.dry_run,
        delete=args.delete,
        transform_upsert=args.transform_upsert,
        err_filter=args.err_filter,
    )


if __name__ == "__main__":
    main()
