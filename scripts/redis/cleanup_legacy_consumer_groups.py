r"""Cleanup legacy Redis Streams consumer groups (underscore names).

This script is intentionally conservative:
- Always creates a backup JSON file of pending messages before making changes.
- By default runs in dry-run mode.

Usage (PowerShell):
  & ".\.venv\Scripts\python.exe" scripts\cleanup_legacy_consumer_groups.py
  & ".\.venv\Scripts\python.exe" scripts\cleanup_legacy_consumer_groups.py --apply

Environment:
- REDIS_URL (loaded from .env / deployment/.env if present)
- TENANT_ID (default: agentic-dev)

What it does (when --apply is provided):
- For each legacy group, backs up pending messages (PEL) to artifacts/...
- XACKs all pending message IDs in the legacy group
- XGROUP DESTROYs the legacy group

Notes:
- Destroying a consumer group deletes its PEL state. Stream entries remain.
- We only ACK pending messages to allow safe group destruction.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
import redis


@dataclass
class PendingMessage:
    message_id: str
    consumer: Optional[str]
    idle_ms: Optional[int]
    deliveries: Optional[int]
    fields: Dict[str, Any]


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_env() -> None:
    root = _repo_root()
    load_dotenv(root / ".env", override=False)
    load_dotenv(root / "deployment" / ".env", override=False)


def _redis_client(redis_url: str) -> redis.Redis:
    return redis.Redis.from_url(redis_url, decode_responses=True)


def _xinfo_group_names(r: redis.Redis, stream: str) -> List[str]:
    try:
        groups = r.xinfo_groups(stream)
    except Exception:
        return []

    names: List[str] = []
    for g in groups:
        name = g.get("name")
        if isinstance(name, (bytes, bytearray)):
            name = name.decode("utf-8", errors="ignore")
        if isinstance(name, str):
            names.append(name)
    return names


def _pending_messages(
    r: redis.Redis,
    stream: str,
    group: str,
    limit: int = 1000,
) -> List[PendingMessage]:
    summary = r.xpending(stream, group)
    pending_count = int(summary.get("pending", 0) or 0)
    if pending_count == 0:
        return []

    # Pull a bounded list of pending entries.
    entries = r.xpending_range(stream, group, min="-", max="+", count=min(limit, pending_count))
    out: List[PendingMessage] = []
    for p in entries:
        message_id = p.get("message_id")
        if not message_id:
            continue
        consumer = p.get("consumer")
        idle_ms = p.get("time_since_delivered")
        deliveries = p.get("times_delivered")

        rows = r.xrange(stream, min=message_id, max=message_id)
        fields: Dict[str, Any] = rows[0][1] if rows else {}

        out.append(
            PendingMessage(
                message_id=message_id,
                consumer=consumer,
                idle_ms=int(idle_ms) if idle_ms is not None else None,
                deliveries=int(deliveries) if deliveries is not None else None,
                fields=fields,
            )
        )

    return out


def _write_backup(backup_path: Path, payload: Dict[str, Any]) -> None:
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Cleanup legacy underscore consumer groups.")
    parser.add_argument("--apply", action="store_true", help="Actually ACK + destroy legacy groups (default is dry-run).")
    parser.add_argument("--tenant", default=None, help="Tenant ID (default: TENANT_ID env or agentic-dev)")
    args = parser.parse_args()

    _load_env()

    redis_url = (Path(_repo_root() / ".env").read_text(encoding="utf-8") if False else None)  # keep mypy calm
    import os

    redis_url = os.environ.get("REDIS_URL")
    if not redis_url:
        raise SystemExit("REDIS_URL is not set (expected in .env or deployment/.env)")

    tenant = args.tenant or os.environ.get("TENANT_ID", "agentic-dev")

    targets: List[Tuple[str, str, str]] = [
        (f"{tenant}:agents:persistence:tasks", "persistence_workers", "persistence-workers"),
        (f"{tenant}:agents:copywriter:tasks", "copywriter_workers", "copywriter-workers"),
    ]

    r = _redis_client(redis_url)

    backup: Dict[str, Any] = {
        "tenant": tenant,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "redis_host": redis_url.split("@")[(-1)],
        "apply": bool(args.apply),
        "targets": [],
    }

    for stream, legacy_group, canonical_group in targets:
        groups = _xinfo_group_names(r, stream)
        target_info: Dict[str, Any] = {
            "stream": stream,
            "legacy_group": legacy_group,
            "canonical_group": canonical_group,
            "existing_groups": groups,
            "pending_backup": [],
            "actions": [],
        }

        if canonical_group not in groups:
            target_info["actions"].append(f"SKIP: canonical group '{canonical_group}' not found")
            backup["targets"].append(target_info)
            continue

        if legacy_group not in groups:
            target_info["actions"].append("SKIP: legacy group not found")
            backup["targets"].append(target_info)
            continue

        pending = _pending_messages(r, stream, legacy_group, limit=1000)
        target_info["pending_backup"] = [asdict(p) for p in pending]
        target_info["actions"].append(f"FOUND: {len(pending)} pending messages")

        if args.apply:
            # ACK all pending messages so the group can be destroyed cleanly.
            if pending:
                ids = [p.message_id for p in pending]
                # redis-py xack supports multiple IDs
                r.xack(stream, legacy_group, *ids)
                target_info["actions"].append(f"XACK: {len(ids)} message(s)")

            # Destroy the legacy group.
            destroyed = r.xgroup_destroy(stream, legacy_group)
            target_info["actions"].append(f"XGROUP DESTROY: {bool(destroyed)}")

            # Confirm legacy group removed.
            target_info["existing_groups_after"] = _xinfo_group_names(r, stream)

        backup["targets"].append(target_info)

    # Always write backup to disk.
    root = _repo_root()
    backup_path = root / "artifacts" / f"legacy_consumer_groups_backup_{tenant}_{_utc_stamp()}.json"
    _write_backup(backup_path, backup)

    print(f"Backup written: {backup_path}")
    for t in backup["targets"]:
        print(f"\n{t['stream']}")
        for a in t.get("actions", []):
            print(f"  - {a}")
        if "existing_groups_after" in t:
            print(f"  - groups_after: {t['existing_groups_after']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
