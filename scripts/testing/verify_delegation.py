#!/usr/bin/env python
"""
Simple verification that Manager -> Leads delegation is working
"""
import os
import json
import time
import redis

os.environ.setdefault('REDIS_URL', os.getenv('REDIS_URL', 'redis://localhost:6379/0'))
os.environ.setdefault('TENANT_ID', os.getenv('TENANT_ID', 'agentic-dev'))

redis_url = os.getenv('REDIS_URL')
tenant_id = os.getenv('TENANT_ID')
client = redis.Redis.from_url(redis_url, decode_responses=True)

print("Manager -> Leads Delegation Verification")
print("=" * 60)
print()

# Check current stream lengths
manager_len = client.xlen(f'{tenant_id}:manager:tasks')
leads_len = client.xlen(f'{tenant_id}:orchestrators:leads:tasks')
manager_results = client.xlen(f'{tenant_id}:manager:results')
leads_results = client.xlen(f'{tenant_id}:orchestrators:leads:results')

print(f"BEFORE sending test message:")
print(f"  agentic-dev:manager:tasks: {manager_len}")
print(f"  agentic-dev:leads:tasks: {leads_len}")
print(f"  agentic-dev:manager:results: {manager_results}")
print(f"  agentic-dev:leads:results: {leads_results}")
print()

# Send test message
task_id = f"verify-{int(time.time())}"
task_data = {
    "task_id": task_id,
    "goal": "Find AI startups in San Francisco",
    "criteria": {"location": "San Francisco"},
}

print(f"Sending test message to manager:tasks...")
client.xadd(
    f'{tenant_id}:manager:tasks',
    {"payload": json.dumps(task_data), "task_id": task_id}
)
print("Message sent. Waiting 5 seconds for processing...")
print()

# Wait and check
time.sleep(5)

manager_len2 = client.xlen(f'{tenant_id}:manager:tasks')
leads_len2 = client.xlen(f'{tenant_id}:orchestrators:leads:tasks')
manager_results2 = client.xlen(f'{tenant_id}:manager:results')
leads_results2 = client.xlen(f'{tenant_id}:orchestrators:leads:results')

print(f"AFTER processing:")
print(f"  agentic-dev:manager:tasks: {manager_len2} (was {manager_len})")
print(f"  agentic-dev:leads:tasks: {leads_len2} (was {leads_len})")
print(f"  agentic-dev:manager:results: {manager_results2} (was {manager_results})")
print(f"  agentic-dev:leads:results: {leads_results2} (was {leads_results})")
print()

# Verify delegation happened
if leads_len2 > leads_len:
    print("[OK] DELEGATION SUCCESSFUL!")
    print(f"     Task was delegated to leads:tasks ({leads_len2 - leads_len} new message)")
else:
    print("[WARNING] No delegation detected to leads:tasks")

if manager_results2 > manager_results:
    print(f"[OK] Manager completed task ({manager_results2 - manager_results} new result)")
else:
    print("[WARNING] No manager result")
