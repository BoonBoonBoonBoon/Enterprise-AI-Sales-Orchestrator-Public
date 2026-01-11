"""
Send a test task to Manager for full pipeline testing.

Flow: Manager → Leads Orchestrator → RAG Agent → Results upstream

Usage:
    python scripts/testing/send_manager_test.py
"""

import redis
import os
import sys
import json
import uuid
import time
from pathlib import Path
from datetime import datetime, timezone

# Add project root to path
repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo_root))

from dotenv import load_dotenv
load_dotenv(repo_root / ".env")

from core.envelope import task as create_task_envelope, to_redis_fields

# Config
REDIS_URL = os.getenv('REDIS_URL')
TENANT = 'agentic-dev'

client = redis.from_url(REDIS_URL, decode_responses=True)


def send_task(goal: str, data: dict) -> str:
    """Send a task to Manager and return task_id."""
    task_id = f"e2e-{uuid.uuid4().hex[:8]}"
    
    # Create proper envelope using core.envelope
    envelope = create_task_envelope(
        source="e2e_test",
        task_id=task_id,
        payload={
            "goal": goal,
            "data": data
        },
        destination="manager",
        tenant_id=TENANT
    )
    
    msg_id = client.xadd(f"{TENANT}:manager:tasks", to_redis_fields(envelope))
    print(f"✓ Sent task {task_id}")
    print(f"  Message ID: {msg_id}")
    print(f"  Goal: {goal}")
    return task_id


def check_stream_counts():
    """Show current stream message counts."""
    streams = [
        f"{TENANT}:manager:tasks",
        f"{TENANT}:manager:results", 
        f"{TENANT}:leads:tasks",
        f"{TENANT}:leads:results",
        f"{TENANT}:agents:rag:tasks",
        f"{TENANT}:agents:rag:results",
    ]
    
    print("\n--- Stream Status ---")
    for s in streams:
        try:
            count = client.xlen(s)
            print(f"  {s.split(':')[-2]}:{s.split(':')[-1]}: {count}")
        except:
            print(f"  {s}: N/A")


def wait_for_result(task_id: str, timeout: int = 60):
    """Poll for result in manager:results stream."""
    print(f"\n⏳ Waiting for result (timeout: {timeout}s)...")
    
    start = time.time()
    checked_ids = set()
    
    while time.time() - start < timeout:
        # Read latest messages from manager results
        messages = client.xrevrange(f"{TENANT}:manager:results", count=20)
        
        for msg_id, data in messages:
            if msg_id in checked_ids:
                continue
            checked_ids.add(msg_id)
            
            # Check if this is our task
            if data.get("task_id") == task_id:
                print(f"\n✓ RESULT RECEIVED!")
                print(f"  Task ID: {task_id}")
                print(f"  Status: {data.get('status', 'unknown')}")
                
                # Parse payload
                payload = data.get("payload", "{}")
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except:
                        pass
                
                print(f"  Payload: {json.dumps(payload, indent=2)[:500]}")
                return data
        
        time.sleep(2)
    
    print(f"\n⚠ Timeout - no result after {timeout}s")
    return None


def main():
    print("=" * 60)
    print("  MANAGER → LEADS → RAG PIPELINE TEST")
    print("=" * 60)
    
    check_stream_counts()
    
    # Send a real-looking lead enrichment task
    print("\n--- Sending Test Task ---")
    task_id = send_task(
        goal="Find and enrich information about this lead: John Smith from Acme Corporation. Get their contact details and company info.",
        data={
            "name": "John Smith",
            "company": "Acme Corporation", 
            "email": "john.smith@acme.com",
            "entity_type": "lead"
        }
    )
    
    # Wait for result
    result = wait_for_result(task_id, timeout=90)
    
    # Final status
    print("\n--- Final Stream Status ---")
    check_stream_counts()
    
    if result:
        print("\n✓ Pipeline test COMPLETE")
    else:
        print("\n⚠ Check consumer logs for errors")


if __name__ == "__main__":
    main()
