#!/usr/bin/env python
"""Check persistence result for the latest staging task."""
import redis
import os
import json
from dotenv import load_dotenv
load_dotenv()

r = redis.Redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379'))

# Find the result for persist_compound_93e83cac-a371-483b-977d-dfa8f89ed2e8
print("=== Looking for persistence result ===")
results = r.xrevrange('agentic-dev:agents:persistence:results', count=20)
for msg_id, data in results:
    d = json.loads(data.get(b'data', b'{}'))
    task_id = d.get('task_id', d.get('metadata', {}).get('task_id'))
    if 'persist_compound_93e83cac' in str(task_id):
        payload = d.get('payload', {})
        print(f"Task ID: {task_id}")
        print(f"  msg_id: {msg_id.decode()}")
        print(f"  Success: {payload.get('success')}")
        print(f"  Total steps: {payload.get('total_steps')}")
        print(f"  Completed: {payload.get('completed_steps')}")
        print(f"  Failed: {payload.get('failed_step')}")
        print()
        print("Step Results:")
        for step in payload.get('step_results', []):
            print(f"  {step.get('step_name')} ({step.get('table')}):")
            print(f"    operation: {step.get('operation')}")
            print(f"    status: {step.get('status')}")
            print(f"    records_affected: {step.get('records_affected')}")
            if step.get('error'):
                print(f"    error: {step.get('error')}")
        break
else:
    print("Task not found in results yet!")
    print("Latest 5 result task_ids:")
    for i, (msg_id, data) in enumerate(results[:5]):
        d = json.loads(data.get(b'data', b'{}'))
        print(f"  {d.get('task_id', d.get('metadata', {}).get('task_id'))}")
