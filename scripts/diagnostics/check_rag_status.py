#!/usr/bin/env python
"""Check RAG consumer group and task status."""

import sys
import json
from pathlib import Path

# Add project root to path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

try:
    from services.redis import RedisPubSub
except ImportError:
    from services.redis import RedisStreamsClient as RedisPubSub

from core.envelope import from_redis_message


def check_rag_status(tenant_id: str = "agentic-dev"):
    """Check RAG agent consumer status."""
    
    redis_client = RedisPubSub().client
    task_stream = f"{tenant_id}:agents:rag:tasks"
    result_stream = f"{tenant_id}:agents:rag:results"
    consumer_group = "rag-workers"
    
    print(f"""
╔════════════════════════════════════════════════════════════════════╗
║  RAG Agent Status Check                                            ║
╚════════════════════════════════════════════════════════════════════╝

Checking:
  Task Stream: {task_stream}
  Result Stream: {result_stream}
  Consumer Group: {consumer_group}
  Tenant: {tenant_id}
""")
    
    # Check task stream stats
    task_info = redis_client.xinfo_stream(task_stream)
    print(f"\n📤 Task Stream Stats:")
    print(f"   Total tasks: {task_info['length']}")
    print(f"   First ID: {task_info.get('first-entry', ['N/A'])[0]}")
    print(f"   Last ID: {task_info.get('last-entry', ['N/A'])[0]}")
    
    # Check result stream stats
    result_info = redis_client.xinfo_stream(result_stream)
    print(f"\n📥 Result Stream Stats:")
    print(f"   Total results: {result_info['length']}")
    print(f"   First ID: {result_info.get('first-entry', ['N/A'])[0]}")
    print(f"   Last ID: {result_info.get('last-entry', ['N/A'])[0]}")
    
    # Check consumer group
    try:
        groups = redis_client.xinfo_groups(task_stream)
        print(f"\n👥 Consumer Groups:")
        for group_info in groups:
            group_name = group_info.get('name', b'unknown').decode() if isinstance(group_info.get('name'), bytes) else str(group_info.get('name'))
            consumers = group_info.get('consumers', 0)
            pending = group_info.get('pending', 0)
            print(f"\n   Group: {group_name}")
            print(f"   Active Consumers: {consumers}")
            print(f"   Pending Messages: {pending}")
            
            # List consumers in this group
            if consumers > 0:
                consumer_list = redis_client.xinfo_consumers(task_stream, group_name)
                for consumer in consumer_list:
                    consumer_name = consumer.get('name', b'unknown').decode() if isinstance(consumer.get('name'), bytes) else str(consumer.get('name'))
                    idle_ms = consumer.get('idle', 0)
                    pending_count = consumer.get('pending', 0)
                    print(f"     └─ {consumer_name} (idle: {idle_ms}ms, pending: {pending_count})")
    except Exception as e:
        print(f"\n⚠️  Consumer group not found: {e}")
        print(f"   Create group or start RAG consumer to begin processing")
    
    # Check recent tasks
    print(f"\n📋 Recent Tasks (last 3):")
    recent_tasks = redis_client.xrevrange(task_stream, count=3)
    for i, (msg_id, fields) in enumerate(recent_tasks, 1):
        try:
            env = from_redis_message(fields)
            task_id = env.metadata.get('task_id', 'unknown')
            goal = env.payload.get('goal', 'N/A')
            print(f"   {i}. Task {task_id[:8]}... → {goal}")
        except Exception as e:
            print(f"   {i}. [Parse error]")
    
    # Check recent results
    print(f"\n📊 Recent Results (last 3):")
    recent_results = redis_client.xrevrange(result_stream, count=3)
    for i, (msg_id, fields) in enumerate(recent_results, 1):
        try:
            # Try to parse as envelope
            result_dict = dict(fields)
            # Decode bytes keys/values if needed
            decoded = {
                (k.decode() if isinstance(k, bytes) else k): 
                (v.decode() if isinstance(v, bytes) else v)
                for k, v in result_dict.items()
            }
            status = decoded.get('status', 'UNKNOWN')
            print(f"   {i}. Status: {status}")
        except Exception as e:
            print(f"   {i}. [Parse error]")
    
    print(f"\n{'='*70}\n")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Check RAG agent status")
    parser.add_argument("--tenant", default="agentic-dev", help="Tenant ID")
    args = parser.parse_args()
    
    check_rag_status(tenant_id=args.tenant)
