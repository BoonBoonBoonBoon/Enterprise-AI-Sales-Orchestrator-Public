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

from services.redis import RedisStreamsClient as RedisPubSub
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
    """Print a compact overview of all known streams and their lengths."""
    pairs = [
        # RAG
        (rconf.full_key(rconf.STREAM_TASKS), "rag:tasks"),
        (rconf.full_key(rconf.STREAM_RESULTS), "rag:results"),
        (rconf.full_key(getattr(rconf, "STREAM_DLQ", "rag:dlq")), "rag:dlq"),
        # Persistence
        (rconf.full_key(rconf.STREAM_TASKS_WRITE), "persist:tasks"),
        (rconf.full_key(rconf.STREAM_RESULTS_WRITE), "persist:results"),
        (rconf.full_key(getattr(rconf, "STREAM_DLQ_WRITE", "persist:dlq")), "persist:dlq"),
        # Copywriter
        (rconf.full_key(getattr(rconf, "STREAM_TASKS_COPY", "copy:tasks")), "copy:tasks"),
        (rconf.full_key(getattr(rconf, "STREAM_RESULTS_COPY", "copy:results")), "copy:results"),
        (rconf.full_key(getattr(rconf, "STREAM_DLQ_COPY", "copy:dlq")), "copy:dlq"),
        # Orchestrator
        (rconf.full_key(getattr(rconf, "STREAM_ORCHESTRATOR_COMMANDS", "orchestrator:commands")), "orchestrator:commands"),
        # Audit
        (rconf.full_key(getattr(rconf, "STREAM_AUDIT_EVENTS", "audit:events")), "audit:events"),
    ]
    print("\n=== Overview (Stream Lengths) ===")
    for key, label in pairs:
        ln = _xinfo_len(client, key)
        print(f"{label:<24} {key} length={ln if ln is not None else 'n/a'}")


def inspect_workflow_state(client, verbose: bool = False, sample: int = 10) -> None:
    """Inspect workflow:state:* keys to show active workflows."""
    pattern = rconf.full_key("workflow:state:*")
    total = 0
    samples = []
    try:
        for key in client.scan_iter(match=pattern, count=100):
            total += 1
            if len(samples) < sample:
                try:
                    data = client.hgetall(key)
                    ttl = client.ttl(key)
                    correlation_id = str(key).split(":")[-1]
                    samples.append({
                        "correlation_id": correlation_id,
                        "ttl": ttl,
                        "data": data
                    })
                except Exception:
                    pass
    except Exception as e:
        print(f"\n=== Workflow State ===\nerror scanning workflow state: {e}")
        return

    print("\n=== Workflow State (workflow:state:*) ===")
    print(f"total active workflows: {total}")
    if samples:
        print("sample workflows:")
        for s in samples:
            status = s["data"].get("status", "unknown")
            task_count = s["data"].get("task_count", "0")
            completed = s["data"].get("completed_count", "0")
            print(f"  - correlation_id={s['correlation_id'][:16]}... status={status} tasks={task_count} completed={completed} ttl={s['ttl']}s")
        if verbose:
            _safe_print("sample_raw:", samples)
    else:
        print("(no active workflows)")


def check_alert_thresholds(client) -> None:
    """Check health metrics against alerting thresholds."""
    print("\n=== Alert Threshold Checks ===")
    
    alerts = []
    
    # Define thresholds
    MAX_PENDING = 1000
    MAX_DLQ_LENGTH = 100
    MAX_CONSUMER_IDLE_MS = 300000  # 5 minutes
    
    # Check pending counts for all consumer groups
    groups_to_check = [
        (rconf.full_key(rconf.STREAM_TASKS), rconf.GROUP_WORKERS, "rag-workers"),
        (rconf.full_key(rconf.STREAM_TASKS_WRITE), rconf.GROUP_WRITERS, "persist-writers"),
        (rconf.full_key(getattr(rconf, "STREAM_TASKS_COPY", "copy:tasks")), getattr(rconf, "GROUP_COPY_WRITERS", "copy-writers"), "copy-writers"),
        (rconf.full_key(getattr(rconf, "STREAM_ORCHESTRATOR_COMMANDS", "orchestrator:commands")), getattr(rconf, "GROUP_ORCHESTRATORS", "orchestrators"), "orchestrators"),
    ]
    
    for stream_key, group, label in groups_to_check:
        try:
            pending = client.xpending(stream_key, group)
            if pending and isinstance(pending, dict):
                count = pending.get("pending", 0)
                if count > MAX_PENDING:
                    alerts.append(f"⚠️  HIGH PENDING: {label} has {count} pending messages (threshold: {MAX_PENDING})")
        except Exception:
            pass
    
    # Check DLQ lengths
    dlq_streams = [
        (rconf.full_key(getattr(rconf, "STREAM_DLQ", "rag:dlq")), "rag:dlq"),
        (rconf.full_key(getattr(rconf, "STREAM_DLQ_WRITE", "persist:dlq")), "persist:dlq"),
        (rconf.full_key(getattr(rconf, "STREAM_DLQ_COPY", "copy:dlq")), "copy:dlq"),
    ]
    
    for key, label in dlq_streams:
        ln = _xinfo_len(client, key)
        if ln and ln > MAX_DLQ_LENGTH:
            alerts.append(f"⚠️  DLQ GROWTH: {label} has {ln} messages (threshold: {MAX_DLQ_LENGTH})")
    
    # Check for stale consumers
    for stream_key, group, label in groups_to_check:
        try:
            consumers = client.xinfo_consumers(stream_key, group)
            if consumers:
                for c in consumers:
                    idle_ms = c.get("idle", 0)
                    if idle_ms > MAX_CONSUMER_IDLE_MS:
                        consumer_name = c.get("name", "unknown")
                        alerts.append(f"⚠️  STALE CONSUMER: {label}/{consumer_name} idle for {idle_ms/1000:.0f}s (threshold: {MAX_CONSUMER_IDLE_MS/1000:.0f}s)")
        except Exception:
            pass
    
    # Check heartbeat presence
    services = ["rag", "persist", "copy", "orchestrator"]
    for service in services:
        pattern = rconf.full_key(f"ops:hb:{service}:*")
        count = sum(1 for _ in client.scan_iter(match=pattern, count=10))
        if count == 0:
            alerts.append(f"⚠️  NO HEARTBEATS: No active {service} workers detected")
    
    if alerts:
        for alert in alerts:
            print(alert)
    else:
        print("✅ All metrics within normal thresholds")


def check_message_latency(client, stream_key: str, label: str, sample: int = 10) -> None:
    """Check age of oldest pending messages to detect processing lag."""
    try:
        # Get oldest pending messages
        pending = client.xpending_range(stream_key, "-", "+", count=sample)
        if pending:
            import time
            now_ms = int(time.time() * 1000)
            
            print(f"\n=== Latency: {label} ===")
            for entry in pending:
                msg_id = entry["message_id"]
                # Parse timestamp from message ID (format: timestamp-sequence)
                try:
                    msg_ts_ms = int(str(msg_id).split("-")[0])
                    age_ms = now_ms - msg_ts_ms
                    age_sec = age_ms / 1000
                    consumer = entry.get("consumer", "unknown")
                    times_delivered = entry.get("times_delivered", 0)
                    print(f"  - msg_id={msg_id} age={age_sec:.1f}s consumer={consumer} deliveries={times_delivered}")
                except Exception:
                    pass
    except Exception as e:
        print(f"latency check error for {label}: {e}")


def inspect_dlq(client, verbose: bool = False, sample: int = 3) -> None:
    """Display DLQ stream lengths and up to `sample` entries for each."""
    dlqs = [
        (rconf.full_key(getattr(rconf, "STREAM_DLQ", "rag:dlq")), "rag:dlq"),
        (rconf.full_key(getattr(rconf, "STREAM_DLQ_WRITE", "persist:dlq")), "persist:dlq"),
        (rconf.full_key(getattr(rconf, "STREAM_DLQ_COPY", "copy:dlq")), "copy:dlq"),
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
    ap = argparse.ArgumentParser(description="Comprehensive Redis Streams Health Monitor")
    ap.add_argument("--section", choices=["rag", "persist", "copy", "orchestrator", "audit", "all"], default="all",
                    help="Which streams to inspect (default: all)")
    ap.add_argument("--verbose", action="store_true", help="Show detailed raw data")
    ap.add_argument("--check-latency", action="store_true", help="Check message processing latency")
    ap.add_argument("--alert-thresholds", action="store_true", help="Check health metrics against alerting thresholds")
    args = ap.parse_args()

    r = RedisPubSub()
    client = r.client  # low-level redis client

    print("=" * 80)
    print("Redis Streams Health Monitor")
    print("=" * 80)
    print("Using REDIS_URL:", os.getenv("REDIS_URL", "(default / local)"))
    print("Namespace:", rconf.NAMESPACE)

    # Compact overview of all known streams
    overview_known_streams(client)

    # Inspect streams by section
    if args.section in ("rag", "all"):
        inspect_stream(client, rconf.STREAM_TASKS, rconf.GROUP_WORKERS, verbose=args.verbose)
        inspect_stream(client, rconf.STREAM_RESULTS, None, verbose=args.verbose)
        if args.check_latency:
            check_message_latency(client, rconf.full_key(rconf.STREAM_TASKS), "rag:tasks")

    if args.section in ("persist", "all"):
        inspect_stream(client, rconf.STREAM_TASKS_WRITE, rconf.GROUP_WRITERS, verbose=args.verbose)
        inspect_stream(client, rconf.STREAM_RESULTS_WRITE, None, verbose=args.verbose)
        if args.check_latency:
            check_message_latency(client, rconf.full_key(rconf.STREAM_TASKS_WRITE), "persist:tasks")

    if args.section in ("copy", "all"):
        copy_tasks = getattr(rconf, "STREAM_TASKS_COPY", "copy:tasks")
        copy_results = getattr(rconf, "STREAM_RESULTS_COPY", "copy:results")
        copy_group = getattr(rconf, "GROUP_COPY_WRITERS", "copy-writers")
        inspect_stream(client, copy_tasks, copy_group, verbose=args.verbose)
        inspect_stream(client, copy_results, None, verbose=args.verbose)
        if args.check_latency:
            check_message_latency(client, rconf.full_key(copy_tasks), "copy:tasks")

    if args.section in ("orchestrator", "all"):
        orch_commands = getattr(rconf, "STREAM_ORCHESTRATOR_COMMANDS", "orchestrator:commands")
        orch_group = getattr(rconf, "GROUP_ORCHESTRATORS", "orchestrators")
        inspect_stream(client, orch_commands, orch_group, verbose=args.verbose)
        if args.check_latency:
            check_message_latency(client, rconf.full_key(orch_commands), "orchestrator:commands")

    if args.section in ("audit", "all"):
        audit_events = getattr(rconf, "STREAM_AUDIT_EVENTS", "audit:events")
        inspect_stream(client, audit_events, None, verbose=args.verbose)

    # Workflow state tracking (always show if present)
    if args.section == "all":
        inspect_workflow_state(client, verbose=args.verbose)

    # Heartbeats are global; show always
    inspect_heartbeats(r, verbose=args.verbose)
    
    # DLQs are global; show always
    inspect_dlq(client, verbose=args.verbose)

    # Alert threshold checks
    if args.alert_thresholds:
        check_alert_thresholds(client)

    r.close()
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
