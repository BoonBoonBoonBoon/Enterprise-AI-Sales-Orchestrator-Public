"""Redis Streams group reset helper (SAFE)

What this helper does (at a glance):
- Create or recreate consumer groups for task streams (RAG and/or persistence).
- Optionally set the group read cursor (SETID) to either '$' (new-only) or '0-0' (replay all).
- Never deletes the stream or messages. It only (re)creates groups and adjusts their cursors.

Common use cases:
- Fresh benchmark: set the group to '$' so workers only consume new messages.
- Backfill/replay: set the group to '0-0' to re-deliver all historical messages to the group.

Safety:
- Asks for explicit confirmation unless --yes is provided.
- Only operates on task streams (rag:tasks, persist:tasks) to avoid accidental changes to results streams.

Usage (PowerShell):
  # Set both groups to consume only new messages
  python scripts/streams_group_reset.py --section both --setid $

  # Replay all historical messages for persist tasks group
  python scripts/streams_group_reset.py --section persist --setid 0-0

  # Recreate group from scratch (e.g., if it doesn’t exist or you want a clean cursor)
  python scripts/streams_group_reset.py --section rag --recreate --setid $

Options:
  --section rag|persist|both     Which task streams to operate on (default: both)
  --recreate                     Try to destroy and recreate the group (if existing)
  --setid ID                     Set the group cursor to a specific ID ('$' for new-only, '0-0' for replay)
  --yes                          Skip interactive confirmation
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.tools.redis.client import RedisPubSub
from agent.tools.redis import config as rconf


def ensure_group(client, stream_key: str, group: str, setid: str | None, recreate: bool) -> None:
    # Create stream if missing by adding a dummy that’s immediately trimmed
    try:
        client.xinfo_stream(stream_key)
    except Exception:
        try:
            client.xadd(stream_key, {"bootstrap": "1"})
        except Exception:
            pass

    if recreate:
        try:
            client.xgroup_destroy(stream_key, group)
            print(f"Destroyed existing group '{group}' on {stream_key}")
        except Exception:
            pass

    created = False
    try:
        client.xgroup_create(stream_key, group, id=setid or "$", mkstream=True)
        created = True
        print(f"Created group '{group}' on {stream_key} with id={setid or '$'}")
    except Exception as e:
        if "BUSYGROUP" in str(e).upper():
            print(f"Group '{group}' already exists on {stream_key}")
        else:
            raise

    # If not newly created and a setid is requested, attempt setid
    if not created and setid is not None:
        try:
            client.xgroup_setid(stream_key, group, setid)
            print(f"Set group '{group}' id={setid} on {stream_key}")
        except Exception as e:
            print(f"Failed to set group id: {e}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--section", choices=["rag", "persist", "both"], default="both")
    ap.add_argument("--recreate", action="store_true", help="Destroy and recreate the group")
    ap.add_argument("--setid", default=None, help="Set group cursor ('$' for new, '0-0' for replay)")
    ap.add_argument("--yes", action="store_true", help="Skip interactive confirmation")
    args = ap.parse_args()

    r = RedisPubSub()
    client = r.client

    plan = []
    if args.section in ("rag", "both"):
        plan.append((rconf.full_key(rconf.STREAM_TASKS), rconf.GROUP_WORKERS))
    if args.section in ("persist", "both"):
        plan.append((rconf.full_key(rconf.STREAM_TASKS_WRITE), rconf.GROUP_WRITERS))

    print("Using REDIS_URL:", os.getenv("REDIS_URL", "(default / local)"))
    print("Namespace:", rconf.NAMESPACE)
    print("Planned operations:")
    for s, g in plan:
        print(f"  - stream={s} group={g} recreate={args.recreate} setid={args.setid or '$ (create default)'}")

    if not args.yes:
        resp = input("Proceed? Type 'yes' to continue: ").strip().lower()
        if resp != "yes":
            print("Aborted.")
            return

    for stream_key, group in plan:
        try:
            ensure_group(client, stream_key, group, setid=args.setid, recreate=args.recreate)
        except Exception as e:
            print(f"Error on {stream_key} / {group}: {e}")

    r.close()


if __name__ == "__main__":
    main()
