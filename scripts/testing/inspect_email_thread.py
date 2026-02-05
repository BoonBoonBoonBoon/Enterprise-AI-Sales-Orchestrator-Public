import argparse
import json
import os
import pathlib
import sys
from typing import Any, Dict, List

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from services.persistence.adapters.supabase_adapter import SupabaseAdapter


def _load_dotenv(path: str = ".env") -> None:
    p = pathlib.Path(path)
    if not p.exists():
        return
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"')
        os.environ.setdefault(key, value)


def _build_adapter() -> SupabaseAdapter:
    url = os.environ.get("SUPABASE_URL")
    key = (
        os.environ.get("SUPABASE_PERSISTENCE_JWT")
        or os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_KEY")
    )
    anon = os.environ.get("SUPABASE_ANON_KEY")

    if not url or not key:
        raise RuntimeError(
            "Missing SUPABASE_URL and SUPABASE_PERSISTENCE_JWT/SUPABASE_KEY. "
            "Set them in your environment or .env."
        )

    using_custom_jwt = bool(os.environ.get("SUPABASE_PERSISTENCE_JWT") and anon)
    if using_custom_jwt:
        return SupabaseAdapter(url, key, anon_key=anon)
    return SupabaseAdapter(url, key)


def _safe_query(adapter: SupabaseAdapter, table: str, filters: Dict[str, Any], *, limit: int = 50) -> List[Dict[str, Any]]:
    return adapter.query(table, filters=filters, limit=limit, order_by="created_at", descending=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect a specific inbound email thread in Supabase")
    parser.add_argument("--email", required=True)
    parser.add_argument("--thread-id", required=False)
    parser.add_argument("--debug-http", action="store_true", help="Print REST status codes for basic probes")
    args = parser.parse_args()

    _load_dotenv()
    # This is a debug utility; avoid blocking on DNS preflight.
    os.environ.setdefault("SUPABASE_SKIP_DNS_CHECK", "1")
    adapter = _build_adapter()

    email = args.email
    thread_id = args.thread_id

    out: Dict[str, Any] = {
        "env": {
            "have_url": bool(os.environ.get("SUPABASE_URL")),
            "have_persistence_jwt": bool(os.environ.get("SUPABASE_PERSISTENCE_JWT")),
            "have_service_key": bool(os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")),
            "have_anon_key": bool(os.environ.get("SUPABASE_ANON_KEY")),
        },
        "inputs": {"email": email, "thread_id": thread_id},
    }

    out["leads"] = _safe_query(adapter, "leads", {"email": email}, limit=10)
    out["staging_leads"] = _safe_query(adapter, "staging_leads", {"email": email}, limit=10)

    if args.debug_http and not out["leads"] and not out["staging_leads"]:
        try:
            import requests  # type: ignore

            probes = [
                ("leads", {"select": "id,email", "limit": 1}),
                ("staging_leads", {"select": "id,email", "limit": 1}),
            ]
            probe_results = []
            for table, params in probes:
                url = f"{adapter.url}/rest/v1/{table}"
                r = requests.get(url, headers=adapter._rest_headers(), params=params, timeout=15)  # type: ignore[attr-defined]
                probe_results.append(
                    {
                        "table": table,
                        "status_code": r.status_code,
                        "body_preview": (r.text or "")[:400],
                    }
                )
            out["http_probes"] = probe_results
        except Exception as e:
            out["http_probes"] = {"error": str(e)}

    if thread_id:
        out["conversations_by_thread"] = _safe_query(adapter, "conversations", {"thread_id": thread_id}, limit=50)
        out["staging_conversations_by_thread"] = _safe_query(adapter, "staging_conversations", {"thread_id": thread_id}, limit=50)

    # Expand:
    if out["staging_leads"]:
        staging_lead_id = out["staging_leads"][0].get("id")
        staging_convs = adapter.query(
            "staging_conversations",
            filters={"staging_lead_id": staging_lead_id},
            limit=200,
            order_by="created_at",
            descending=False,
        )
        staging_msgs: List[Dict[str, Any]] = []
        for conv in staging_convs:
            cid = conv.get("id")
            if cid:
                staging_msgs.extend(
                    adapter.query(
                        "staging_messages",
                        filters={"staging_conversation_id": cid},
                        limit=200,
                        order_by="created_at",
                        descending=False,
                    )
                )
        out["staging_expanded"] = {
            "staging_lead_id": staging_lead_id,
            "staging_conversations": staging_convs,
            "staging_messages": staging_msgs,
        }

    if out["leads"]:
        lead_id = out["leads"][0].get("id")
        convs = adapter.query(
            "conversations",
            filters={"lead_id": lead_id},
            limit=200,
            order_by="created_at",
            descending=False,
        )
        msgs: List[Dict[str, Any]] = []
        for conv in convs:
            cid = conv.get("id")
            if cid:
                msgs.extend(
                    adapter.query(
                        "messages",
                        filters={"conversation_id": cid},
                        limit=200,
                        order_by="created_at",
                        descending=False,
                    )
                )
        out["leads_expanded"] = {"lead_id": lead_id, "conversations": convs, "messages": msgs}

    print(json.dumps(out, indent=2)[:20000])


if __name__ == "__main__":
    main()
