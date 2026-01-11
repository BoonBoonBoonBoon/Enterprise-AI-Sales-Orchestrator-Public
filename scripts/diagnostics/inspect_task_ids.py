import json
import os
import argparse
from typing import Iterable, Optional

import redis

try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv()
except Exception:
    pass


def get_redis() -> redis.Redis:
    url = (os.getenv("REDIS_URL") or "").strip()
    if url:
        return redis.Redis.from_url(url, decode_responses=True)
    host = os.getenv("REDIS_HOST", "redis")
    port = int(os.getenv("REDIS_PORT", "6379"))
    return redis.Redis(host=host, port=port, decode_responses=True)


def iter_recent(stream: str, count: int = 200) -> Iterable[tuple[str, dict]]:
    r = get_redis()
    for msg_id, fields in r.xrevrange(stream, count=count):
        yield msg_id, fields


def parse_envelope(fields: dict) -> dict:
    data = fields.get("data")
    if not isinstance(data, str):
        return {}
    try:
        return json.loads(data)
    except Exception:
        return {}


def match_task_id(env: dict, task_id: str) -> bool:
    return (env.get("metadata") or {}).get("task_id") == task_id


def match_correlation_id(env: dict, correlation_id: str) -> bool:
    return (env.get("metadata") or {}).get("correlation_id") == correlation_id


def dump_match(label: str, stream: str, msg_id: str, env: dict) -> None:
    meta = env.get("metadata") or {}
    payload = env.get("payload") or {}
    ctx = (payload.get("context") or {}) if isinstance(payload, dict) else {}

    print(f"[{label}] stream={stream} msg_id={msg_id}")
    print(f"  task_id={meta.get('task_id')} correlation_id={meta.get('correlation_id')}")
    print(f"  source={meta.get('source')} destination={meta.get('destination')} tags={meta.get('tags')}")
    if isinstance(payload, dict):
        print(f"  goal={payload.get('goal')}")
        print(f"  payload_keys={list(payload.keys())}")
        print(f"  context_keys={list(ctx.keys())}")
        if "actions_allowed" in ctx:
            print(f"  actions_allowed={ctx.get('actions_allowed')}")
        if "email_event" in ctx:
            ee = ctx.get("email_event") or {}
            if isinstance(ee, dict):
                print(f"  email_event.subject={ee.get('subject')} from={ee.get('from')} to={ee.get('to')}")
    else:
        print(f"  payload_type={type(payload)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect recent Redis Stream envelopes for task_id/correlation_id matches")
    parser.add_argument("--tenant", default=os.getenv("TENANT_ID", "agentic-dev"), help="Tenant id (default: TENANT_ID or agentic-dev)")
    parser.add_argument("--task-id", action="append", default=[], help="Task id to match (repeatable)")
    parser.add_argument("--correlation-id", action="append", default=[], help="Correlation id to match (repeatable)")
    parser.add_argument("--count", type=int, default=500, help="Messages to scan per stream (default: 500)")
    parser.add_argument(
        "--streams",
        nargs="*",
        default=None,
        help="Explicit stream names to scan (defaults to manager/leads/outbound tasks+results)",
    )
    args = parser.parse_args()

    tenant = args.tenant
    task_ids = [x for x in args.task_id if x]
    correlation_ids = [x for x in args.correlation_id if x]

    if not task_ids and not correlation_ids:
        print("No --task-id or --correlation-id provided; nothing to match.")
        print("Example: python scripts/inspect_task_ids.py --correlation-id <uuid>")
        return

    streams = args.streams or [
        f"{tenant}:manager:tasks",
        f"{tenant}:manager:results",
        f"{tenant}:orchestrators:leads:tasks",
        f"{tenant}:orchestrators:leads:results",
        f"{tenant}:orchestrators:outbound:tasks",
        f"{tenant}:orchestrators:outbound:results",
    ]

    found = 0
    for stream in streams:
        for msg_id, fields in iter_recent(stream, count=args.count):
            env = parse_envelope(fields)
            if not env:
                continue
            if any(match_task_id(env, tid) for tid in task_ids) or any(match_correlation_id(env, cid) for cid in correlation_ids):
                found += 1
                dump_match("MATCH", stream, msg_id, env)

    print(f"\nfound_total={found}")


if __name__ == "__main__":
    main()
