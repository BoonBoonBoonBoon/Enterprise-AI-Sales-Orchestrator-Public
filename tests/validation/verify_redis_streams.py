"""Verify Redis Streams Setup.

Env-driven diagnostic script to verify canonical stream naming + consumer groups.
This is NOT a pytest test and should not embed credentials.
"""

import os
import sys

from dotenv import load_dotenv


def verify_streams() -> None:
    load_dotenv()

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from agent.tools.redis.client import RedisPubSub

    tenant_id = os.getenv("TENANT_ID", "agentic-dev")
    redis_pubsub = RedisPubSub()
    redis = redis_pubsub.client

    print("=" * 80)
    print("REDIS STREAMS VERIFICATION")
    print("=" * 80)
    print(f"Tenant: {tenant_id}")
    print()

    expected_streams = {
        # Tier 1
        "manager_tasks": f"{tenant_id}:manager:tasks",
        "manager_results": f"{tenant_id}:manager:results",
        # Tier 2 (canonical hierarchical naming)
        "leads_tasks": f"{tenant_id}:orchestrators:leads:tasks",
        "leads_results": f"{tenant_id}:orchestrators:leads:results",
        "outbound_tasks": f"{tenant_id}:orchestrators:outbound:tasks",
        "outbound_results": f"{tenant_id}:orchestrators:outbound:results",
    }

    print("Checking expected streams...")
    found = []
    missing = []

    for name, stream_key in expected_streams.items():
        try:
            info = redis.xinfo_stream(stream_key)
            length = info.get("length", "?")
            found.append((name, stream_key, length))
            print(f"  ✓ {stream_key} ({length} messages)")
        except Exception as e:
            missing.append((name, stream_key, str(e)))
            print(f"  ✗ {stream_key} ({e})")

    print()
    print("Checking expected consumer groups...")
    expected_groups = {
        f"{tenant_id}:manager:tasks": "manager-workers",
        f"{tenant_id}:orchestrators:leads:tasks": "leads-workers",
        f"{tenant_id}:orchestrators:outbound:tasks": "outbound-workers",
    }

    for stream_key, group_name in expected_groups.items():
        try:
            groups = redis.xinfo_groups(stream_key)
            group_names = [
                (g["name"].decode() if isinstance(g.get("name"), bytes) else g.get("name"))
                for g in groups
            ]
            if group_name in group_names:
                print(f"  ✓ {stream_key} → {group_name}")
            else:
                print(f"  ⚠ {stream_key} missing group {group_name} (have: {group_names})")
        except Exception as e:
            print(f"  ⚠ {stream_key} group check failed ({e})")

    print()
    print("SUMMARY")
    print("-" * 80)
    print(f"Found streams: {len(found)}")
    print(f"Missing/error streams: {len(missing)}")


if __name__ == "__main__":
    verify_streams()
