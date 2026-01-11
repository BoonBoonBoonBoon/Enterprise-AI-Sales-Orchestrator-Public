"""Redis Streams health/visibility

Quickly inspect stream sizes, consumer groups, consumers, and pending counts for
both the RAG and persistence (write) paths.

It uses env-driven names from agent.tools.redis.config, so it works with your
namespaced keys and Cloud REDIS_URL out of the box.

Usage (PowerShell):
  # Inspect both RAG and persist streams (default)
  python scripts/streams_health.py

  # Only RAG streams
  python scripts/streams_health.py --section rag

  # Only persistence streams
  python scripts/streams_health.py --section persist

Options:
  --section rag|persist|both     Which set of streams to inspect (default both)
  --verbose                      Print full raw structures in addition to summary
"""
from __future__ import annotations

import argparse
import json
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


def _safe_print(title: str, data) -> None:
    print(title)
    try:
        print(json.dumps(data, indent=2))
    except Exception:
        print(str(data))


def _xpending_summary(client, stream_key: str, group: str):
    try:
        info = client.xpending(stream_key, group)
        # redis-py returns a dict in recent versions, but be defensive
        if isinstance(info, dict):
            return {
                "pending": info.get("pending"),
                "min": info.get("min"),
                "max": info.get("max"),
                "consumers": info.get("consumers"),
            }
        # older tuple style: (count, min, max, [ (consumer, count), ... ])
        if isinstance(info, (list, tuple)) and len(info) >= 4:
            count, min_id, max_id, consumers = info[0], info[1], info[2], info[3]
            cons_list = []
            try:
                for c in consumers or []:
                    if isinstance(c, (list, tuple)):
                        cons_list.append({"name": c[0], "pending": c[1]})
            except Exception:
                pass
            return {"pending": count, "min": min_id, "max": max_id, "consumers": cons_list}
    except Exception as e:
        return {"error": str(e)}
    return None


def inspect_stream(client, stream_short: str, group: str | None, verbose: bool = False) -> None:
    stream_key = rconf.full_key(stream_short)
    print(f"\n=== Stream: {stream_key} ===")
    try:
        sinfo = client.xinfo_stream(stream_key)
        print(f"length: {sinfo.get('length')} | last-generated-id: {sinfo.get('last-generated-id')}")
        if verbose:
            _safe_print("xinfo_stream:", sinfo)
    except Exception as e:
        print(f"xinfo_stream error: {e}")
        return

    # Groups
    try:
        ginfo = client.xinfo_groups(stream_key)
        if not ginfo:
            print("groups: (none)")
        else:
            print("groups:")
            for g in ginfo:
                print(
                    f"  - name={g.get('name')} consumers={g.get('consumers')} pending={g.get('pending')} last-delivered-id={g.get('last-delivered-id')}"
                )
            if verbose:
                _safe_print("xinfo_groups:", ginfo)
    except Exception as e:
        print(f"xinfo_groups error: {e}")
        ginfo = []

    # Consumers per group (only for the provided group if given; else for each)
    groups_to_check = [group] if group else [g.get("name") for g in (ginfo or []) if isinstance(g, dict)]
    for grp in groups_to_check:
        if not grp:
            continue
        try:
            cinfo = client.xinfo_consumers(stream_key, grp)
            if not cinfo:
                print(f"consumers ({grp}): (none)")
            else:
                print(f"consumers ({grp}):")
                for c in cinfo:
                    print(f"  - name={c.get('name')} pending={c.get('pending')} idle_ms={c.get('idle')}")
                if verbose:
                    _safe_print(f"xinfo_consumers ({grp}):", cinfo)
        except Exception as e:
            print(f"xinfo_consumers ({grp}) error: {e}")

        # XPENDING summary
        xp = _xpending_summary(client, stream_key, grp)
        if xp:
            print(f"xpending ({grp}):", json.dumps(xp, indent=2))


def inspect_heartbeats(r: RedisPubSub, verbose: bool = False, sample: int = 20) -> None:
    """List heartbeat keys (ops:hb:*) with TTLs and summarize by service.

    Uses SCAN to avoid KEYS. Shows up to `sample` entries with TTL values.
    """
    pattern = r._chan("ops:hb:*")  # namespaced pattern
    client = r.client
    total = 0
    per_service = {}
    samples = []
    try:
        for key in client.scan_iter(match=pattern, count=500):
            total += 1
            try:
                # derive service from key ns:ops:hb:{service}:{id}
                parts = str(key).split(":")
                # Remove namespace prefix when present
                # Expect [..., 'ops', 'hb', '{service}', '{id}']
                svc = None
                if len(parts) >= 4:
                    # last 4 parts should be ops,hb,service,id — tolerate extra namespace parts in front
                    svc = parts[-2] if parts[-4] == "ops" and parts[-3] == "hb" else None
                if not svc and len(parts) >= 2:
                    # fallback: try second to last as service
                    svc = parts[-2]
                per_service[svc or "unknown"] = per_service.get(svc or "unknown", 0) + 1
                if len(samples) < sample:
                    ttl = client.ttl(key)
                    samples.append({"key": key, "ttl": ttl})
            except Exception:
                pass
    except Exception as e:
        print(f"\n=== Heartbeats (ops:hb) ===\nerror scanning heartbeats: {e}")
        return

    print("\n=== Heartbeats (ops:hb) ===")
    print(f"total: {total}")
    if per_service:
        print("by service:")
        for svc, cnt in sorted(per_service.items()):
            print(f"  - {svc}: {cnt}")
    if samples:
        print("sample:")
        for s in samples:
            print(f"  - {s['key']} ttl={s['ttl']}")
    if verbose and samples:
        _safe_print("sample_raw:", samples)


def _xinfo_len(client, stream_key: str) -> int | None:
    try:
        info = client.xinfo_stream(stream_key)
        return int(info.get("length", 0))
    except Exception:
        return None


def overview_known_streams(client) -> None:
    """Print a compact overview of known streams and their lengths."""
    pairs = [
        (rconf.full_key(rconf.STREAM_TASKS), "rag:tasks"),
        (rconf.full_key(rconf.STREAM_RESULTS), "rag:results"),
        (rconf.full_key(getattr(rconf, "STREAM_DLQ", "rag:dlq")), "rag:dlq"),
        (rconf.full_key(rconf.STREAM_TASKS_WRITE), "persist:tasks"),
        (rconf.full_key(rconf.STREAM_RESULTS_WRITE), "persist:results"),
        (rconf.full_key(getattr(rconf, "STREAM_DLQ_WRITE", "persist:dlq")), "persist:dlq"),
    ]
    print("\n=== Overview (lengths) ===")
    for key, label in pairs:
        ln = _xinfo_len(client, key)
        print(f"{label:<16} {key} length={ln if ln is not None else 'n/a'}")


def inspect_dlq(client, verbose: bool = False, sample: int = 3) -> None:
    """Display DLQ stream lengths and up to `sample` entries for each."""
    dlqs = [
        (rconf.full_key(getattr(rconf, "STREAM_DLQ", "rag:dlq")), "rag:dlq"),
        (rconf.full_key(getattr(rconf, "STREAM_DLQ_WRITE", "persist:dlq")), "persist:dlq"),
    ]
    for key, label in dlqs:
        print(f"\n=== DLQ: {label} ({key}) ===")
        try:
            info = client.xinfo_stream(key)
            print(f"length: {info.get('length')} | last-generated-id: {info.get('last-generated-id')}")
            if verbose:
                _safe_print("xinfo_stream:", info)
            try:
                rng = client.xrange(key, count=sample)
                if rng:
                    print("sample entries:")
                    for mid, fields in rng:
                        print(f"  - id={mid} fields={fields}")
                else:
                    print("sample: (none)")
            except Exception as e:
                print(f"xrange error: {e}")
        except Exception as e:
            print(f"xinfo_stream error: {e}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--section", choices=["rag", "persist", "both"], default="both")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    r = RedisPubSub()
    client = r.client  # low-level redis client

    print("Using REDIS_URL:", os.getenv("REDIS_URL", "(default / local)"))
    print("Namespace:", rconf.NAMESPACE)

    # Compact overview of known streams
    overview_known_streams(client)

    if args.section in ("rag", "both"):
        inspect_stream(client, rconf.STREAM_TASKS, rconf.GROUP_WORKERS, verbose=args.verbose)
        inspect_stream(client, rconf.STREAM_RESULTS, None, verbose=args.verbose)

    if args.section in ("persist", "both"):
        inspect_stream(client, rconf.STREAM_TASKS_WRITE, rconf.GROUP_WRITERS, verbose=args.verbose)
        inspect_stream(client, rconf.STREAM_RESULTS_WRITE, None, verbose=args.verbose)

    # Heartbeats are global; show always
    inspect_heartbeats(r, verbose=args.verbose)
    # DLQs are global; show always
    inspect_dlq(client, verbose=args.verbose)

    r.close()


if __name__ == "__main__":
    main()
