"""Trace a task/correlation id through Redis Streams.

Usage (PowerShell):
  $env:REDIS_URL='redis://localhost:6379/0'
  $env:TENANT_ID='agentic-dev'
  & ./.venv/Scripts/python.exe ./scripts/testing/trace_stream_id.py a2cf8f27-10eb-4bfd-a5d9-e03528c4be91

Prints any envelopes whose metadata.task_id or metadata.correlation_id match.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Load .env so this script can be run without manually exporting env vars.
# We intentionally override process env to match the repo's configured runtime.
try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv(dotenv_path=ROOT / ".env", override=True)
except Exception:
    pass

from core.envelope import from_redis_message  # noqa: E402
from services.redis import RedisStreamsClient  # noqa: E402


@dataclass
class Hit:
    stream: str
    msg_id: str
    task_id: str
    correlation_id: Optional[str]
    source: str
    destination: Optional[str]
    tenant_id: Optional[str]
    status: str
    payload: Dict[str, Any]
    matched_by: str


def _redact_redis_url(url: str) -> str:
    """Redact credentials in a redis/rediss URL for safe printing."""
    try:
        parts = urlsplit(url)
        netloc = parts.netloc
        if "@" not in netloc:
            return url

        userinfo, hostport = netloc.split("@", 1)
        if ":" in userinfo:
            username, _password = userinfo.split(":", 1)
            safe_userinfo = f"{username}:***"
        else:
            # Password-only or other unusual formats
            safe_userinfo = "***"

        safe_netloc = f"{safe_userinfo}@{hostport}"
        return urlunsplit((parts.scheme, safe_netloc, parts.path, parts.query, parts.fragment))
    except Exception:
        return "<redacted>"


def _summarize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"keys": sorted(payload.keys())}

    # Common reply_packet places
    rp = None
    if isinstance(payload.get("reply_packet"), dict):
        rp = payload["reply_packet"]
    ctx = payload.get("context") if isinstance(payload.get("context"), dict) else None
    if rp is None and isinstance(ctx, dict) and isinstance(ctx.get("reply_packet"), dict):
        rp = ctx["reply_packet"]

    if isinstance(rp, dict):
        facts = rp.get("facts") if isinstance(rp.get("facts"), dict) else {}
        leadres = rp.get("lead_resolution") if isinstance(rp.get("lead_resolution"), dict) else {}
        inbound = rp.get("inbound_email_event") if isinstance(rp.get("inbound_email_event"), dict) else {}
        out["reply_packet"] = {
            "facts.email": facts.get("email"),
            "facts.first_name": facts.get("first_name"),
            "lead_resolution.status": leadres.get("status"),
            "lead_resolution.lead_id": leadres.get("lead_id"),
            "inbound.subject": inbound.get("subject"),
            "inbound.thread_id": inbound.get("thread_id"),
        }

    # RAG-ish operation hints
    if "operation" in payload:
        out["operation"] = payload.get("operation")
    if "entity_type" in payload:
        out["entity_type"] = payload.get("entity_type")

    return out


def _scan_stream(
    r: RedisStreamsClient,
    stream: str,
    target: str,
    *,
    count: int = 1000,
    match_mode: str = "metadata",
) -> List[Hit]:
    key = r._chan(stream)
    try:
        entries = r.client.xrevrange(key, count=count)
    except Exception:
        return []

    hits: List[Hit] = []
    for msg_id, fields in entries:
        # Optional fast path: raw substring match in the stored JSON envelope.
        if match_mode == "contains":
            raw = fields.get("data") if isinstance(fields, dict) else None
            if isinstance(raw, bytes):
                try:
                    raw = raw.decode("utf-8")
                except Exception:
                    raw = None
            if isinstance(raw, str) and target not in raw:
                continue

        try:
            env = from_redis_message(fields)
        except Exception:
            continue

        md = env.metadata
        matched_by = "metadata"
        if match_mode == "metadata":
            if getattr(md, "task_id", None) != target and getattr(md, "correlation_id", None) != target:
                continue
        elif match_mode == "contains":
            matched_by = "contains"
        else:
            raise ValueError(f"Unknown match_mode: {match_mode}")

        payload = env.payload if isinstance(env.payload, dict) else {}
        hits.append(
            Hit(
                stream=stream,
                msg_id=str(msg_id),
                task_id=str(md.task_id),
                correlation_id=getattr(md, "correlation_id", None),
                source=str(md.source),
                destination=getattr(md, "destination", None),
                tenant_id=getattr(md, "tenant_id", None),
                status=str(getattr(env, "status", "")),
                payload=payload,
                matched_by=matched_by,
            )
        )

    return hits


def main(argv: List[str]) -> int:
    if len(argv) < 2:
        print(
            "Usage: trace_stream_id.py <uuid> [--contains] [--stream <stream>] [--msg-id <id>] [--inspect-stream <stream>] [--redis-url <url>] [--tenant <tenant>]"
        )
        return 2

    target = argv[1].strip()
    match_mode = "contains" if "--contains" in argv[2:] else "metadata"

    # Optional: fetch a specific message by stream + id.
    stream_arg: Optional[str] = None
    msg_id_arg: Optional[str] = None
    inspect_stream_arg: Optional[str] = None
    redis_url_arg: Optional[str] = None
    tenant_arg: Optional[str] = None
    if "--stream" in argv[2:]:
        i = argv.index("--stream")
        if i + 1 < len(argv):
            stream_arg = argv[i + 1]
    if "--msg-id" in argv[2:]:
        i = argv.index("--msg-id")
        if i + 1 < len(argv):
            msg_id_arg = argv[i + 1]
    if "--inspect-stream" in argv[2:]:
        i = argv.index("--inspect-stream")
        if i + 1 < len(argv):
            inspect_stream_arg = argv[i + 1]

    if "--redis-url" in argv[2:]:
        i = argv.index("--redis-url")
        if i + 1 < len(argv):
            redis_url_arg = argv[i + 1]

    if "--tenant" in argv[2:]:
        i = argv.index("--tenant")
        if i + 1 < len(argv):
            tenant_arg = argv[i + 1]

    tenant = tenant_arg or os.getenv("TENANT_ID") or os.getenv("REDIS_NAMESPACE") or "agentic-dev"
    url = redis_url_arg or os.getenv("REDIS_URL") or "redis://localhost:6379/0"

    r = RedisStreamsClient(url=url)

    if inspect_stream_arg:
        key = r._chan(inspect_stream_arg)
        print(f"TENANT_ID={tenant}")
        print(f"REDIS_URL={_redact_redis_url(url)}")
        print(f"STREAM={inspect_stream_arg}")
        print(f"KEY={key}")
        try:
            print(f"EXISTS={r.client.exists(key)}")
            print(f"XLEN={r.client.xlen(key)}")
            try:
                info = r.client.xinfo_stream(key)
                if isinstance(info, dict):
                    first = info.get("first-entry")
                    last = info.get("last-entry")
                    print(f"XINFO.length={info.get('length')}")
                    if first and isinstance(first, (list, tuple)) and len(first) >= 1:
                        fid = first[0]
                        fid = fid.decode("utf-8") if isinstance(fid, (bytes, bytearray)) else str(fid)
                        print(f"XINFO.first_id={fid}")
                    if last and isinstance(last, (list, tuple)) and len(last) >= 1:
                        lid = last[0]
                        lid = lid.decode("utf-8") if isinstance(lid, (bytes, bytearray)) else str(lid)
                        print(f"XINFO.last_id={lid}")
            except Exception:
                # XINFO STREAM may be unavailable on some proxies/permissions.
                pass
            last = r.client.xrevrange(key, count=5)
            last_ids = [mid.decode("utf-8") if isinstance(mid, (bytes, bytearray)) else str(mid) for mid, _ in last]
            print(f"LAST_IDS={last_ids}")
        except Exception as e:
            print(f"ERROR={e}")
            return 2
        return 0

    if stream_arg and msg_id_arg:
        key = r._chan(stream_arg)
        try:
            entries = r.client.xrange(key, min=msg_id_arg, max=msg_id_arg)
        except Exception as e:
            print(f"Failed to XRANGE {stream_arg} {msg_id_arg}: {e}")
            return 2

        print(f"TENANT_ID={tenant}")
        print(f"REDIS_URL={_redact_redis_url(url)}")
        print(f"STREAM={stream_arg}")
        print(f"MSG_ID={msg_id_arg}")
        print(f"FOUND={len(entries)}")
        for mid, fields in entries:
            env = from_redis_message(fields)
            md = env.metadata
            payload = env.payload if isinstance(env.payload, dict) else {}
            print("\n---")
            print(f"stream={stream_arg}")
            print(f"msg_id={mid}")
            print(f"task_id={md.task_id}")
            print(f"correlation_id={md.correlation_id}")
            print(f"source={md.source} destination={md.destination} tenant={md.tenant_id} status={env.status}")
            print(_summarize_payload(payload))
        return 0

    streams = [
        f"{tenant}:agents:rag:tasks",
        f"{tenant}:agents:rag:results",
        f"{tenant}:agents:copywriter:tasks",
        f"{tenant}:agents:copywriter:results",
        f"{tenant}:orchestrators:leads:tasks",
        f"{tenant}:orchestrators:leads:results",
        f"{tenant}:orchestrators:outbound:tasks",
        f"{tenant}:orchestrators:outbound:results",
        f"{tenant}:manager:tasks",
        f"{tenant}:manager:results",
    ]

    all_hits: List[Hit] = []
    for s in streams:
        all_hits.extend(_scan_stream(r, s, target, match_mode=match_mode))

    print(f"TENANT_ID={tenant}")
    print(f"REDIS_URL={_redact_redis_url(url)}")
    print(f"TARGET={target}")
    print(f"MATCH_MODE={match_mode}")
    print(f"HITS={len(all_hits)}")

    if not all_hits:
        print("No matching envelopes found in the scanned streams.")
        print("If this UUID is a lead_id or message_id (not an envelope task_id/correlation_id), tell me and I will trace by payload content instead.")
        return 1

    # Print in stream order; if you want strict chronology we can sort by msg_id timestamp.
    for h in all_hits:
        print("\n---")
        print(f"stream={h.stream}")
        print(f"msg_id={h.msg_id}")
        print(f"task_id={h.task_id}")
        print(f"correlation_id={h.correlation_id}")
        print(f"source={h.source} destination={h.destination} tenant={h.tenant_id} status={h.status} matched_by={h.matched_by}")
        print(_summarize_payload(h.payload))

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
