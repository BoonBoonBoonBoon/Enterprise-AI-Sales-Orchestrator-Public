#!/usr/bin/env python
"""Check the result of a specific persistence task."""
import redis
import os
import json
from dotenv import load_dotenv
load_dotenv()

r = redis.Redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379'))

# Check the TASK that was sent
print("=== TASK SENT ===")
msg = r.xrange('agentic-dev:agents:persistence:tasks', min='1767893722218-0', max='1767893722218-0')
if msg:
    msg_id, data = msg[0]
    d = json.loads(data[b'data'])
    payload = d.get('payload', {})
    steps = payload.get('steps', [])
    print('Compound steps sent to persistence:')
    for step in steps:
        print(f"  {step.get('step_name')}: table={step.get('table')}, op={step.get('operation')}")
print()

# Check the RESULT
print("=== RESULT ===")
msg = r.xrange('agentic-dev:agents:persistence:results', min='1767893724656-0', max='1767893724656-0')
if msg:
    msg_id, data = msg[0]
    d = json.loads(data[b'data'])
    payload = d.get('payload', {})
    print('Success:', payload.get('success'))
    print('Total steps:', payload.get('total_steps'))
    print('Completed:', payload.get('completed_steps'))
    print('Skipped:', payload.get('skipped_steps'))
    print('Failed:', payload.get('failed_step'))
    print()
    print('Step Results:')
    for step in payload.get('step_results', []):
        print(f"  {step.get('step_name')} ({step.get('table')}):")
        print(f"    operation: {step.get('operation')}")
        print(f"    status: {step.get('status')}")
        print(f"    records_affected: {step.get('records_affected')}")
        if step.get('skipped_reason'):
            print(f"    skipped_reason: {step.get('skipped_reason')}")
        if step.get('error'):
            print(f"    error: {step.get('error')}")
        print()
