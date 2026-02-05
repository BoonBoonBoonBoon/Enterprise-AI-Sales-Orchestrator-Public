#!/usr/bin/env python
"""Send a test inbound email to manager and trace through to persistence."""
import redis
import os
import json
import uuid
import sys
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

# Ensure project root is on sys.path so imports like `services.*` work
repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo_root))

r = redis.Redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379'))

# Create unique email to avoid matching existing leads
test_email = f"staging_test_{uuid.uuid4().hex[:8]}@example.com"

task = {
    "metadata": {
        "message_id": str(uuid.uuid4()),
        "task_id": f"inbound_test_{uuid.uuid4()}",
        "tenant_id": "agentic-dev",
        "source": "test_script",
        "created_at": datetime.utcnow().isoformat(),
    },
    "payload": {
        "goal": "Handle inbound email event and decide actions",
        "intent": "inbound",
        "context": {
            "context_depth": "deep",
            "actions_allowed": ["store"],
            "email_event": {
                "from": test_email,
                "to": "support@example.com",
                "subject": "Test inbound for staging verification",
                "body": "Testing that inbound emails go to staging tables",
                "received_at": datetime.utcnow().isoformat(),
                "thread_id": None,
                "message_id": str(uuid.uuid4()),
            },
        }
    }
}

print(f"=== Sending inbound email test ===")
print(f"Email: {test_email}")
print(f"Task ID: {task['metadata']['task_id']}")

# Send to manager
msg_id = r.xadd("agentic-dev:manager:tasks", {"data": json.dumps(task)})
print(f"Sent to manager:tasks with msg_id: {msg_id.decode()}")
print()
print("Waiting 25 seconds for processing...")
import time
time.sleep(25)

# Check persistence tasks (last 5)
print("\n=== Recent Persistence Tasks ===")
tasks = r.xrevrange('agentic-dev:agents:persistence:tasks', count=3)
for msg_id, data in tasks:
    d = json.loads(data.get(b'data', b'{}'))
    task_id = d.get('metadata', {}).get('task_id', 'unknown')
    payload = d.get('payload', {})
    steps = payload.get('steps', [])
    print(f"\nTask ID: {task_id}")
    print(f"  msg_id: {msg_id.decode()}")
    print(f"  Steps:")
    for s in steps:
        print(f"    {s.get('step_name')}: table={s.get('table')}, op={s.get('operation')}")

# Check for our test email in staging_leads
print("\n=== Checking Supabase staging_leads ===")
from services.persistence import build_supabase_service
try:
    svc = build_supabase_service()
    leads = svc.query("staging_leads", {"email": test_email}, limit=10)
    if leads:
        print(f"SUCCESS! Found {len(leads)} record(s) in staging_leads:")
        for row in leads:
            print(f"  id={row.get('id')}, email={row.get('email')}, created_at={row.get('created_at')}")

        staging_lead_id = leads[0].get("id")
        if staging_lead_id:
            conversations = svc.query(
                "staging_conversations",
                {"staging_lead_id": staging_lead_id},
                limit=20,
                order_by="created_at",
                descending=True,
            )
            print(f"\nFound {len(conversations)} record(s) in staging_conversations for staging_lead_id={staging_lead_id}")
            if conversations:
                staging_conversation_id = conversations[0].get("id")
                print(f"  latest staging_conversation.id={staging_conversation_id}")
                if staging_conversation_id:
                    messages = svc.query(
                        "staging_messages",
                        {"staging_conversation_id": staging_conversation_id},
                        limit=50,
                        order_by="created_at",
                        descending=True,
                    )
                    print(f"Found {len(messages)} record(s) in staging_messages for staging_conversation_id={staging_conversation_id}")
    else:
        print(f"NOT FOUND in staging_leads. Check persistence logs.")
except Exception as e:
    print(f"Error querying Supabase: {e}")
