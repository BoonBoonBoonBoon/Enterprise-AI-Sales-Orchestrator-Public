#!/usr/bin/env python
"""Diagnose why a specific persistence task may not have been processed."""
import redis
import os
import json
from dotenv import load_dotenv
load_dotenv()

r = redis.Redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379'))

# The task ID from the test
target_task_id = 'persist_compound_da7a07b1-b471-4353-8a5a-5262764bb199'
stream = 'agentic-dev:agents:persistence:tasks'
result_stream = 'agentic-dev:agents:persistence:results'

print(f"Looking for task: {target_task_id}")
print(f"Stream: {stream}")
print()

# Search recent messages for this task
msgs = r.xrevrange(stream, count=100)
found_task = None
for msg_id, data in msgs:
    if target_task_id.encode() in str(data).encode():
        found_task = (msg_id, data)
        break

if found_task:
    msg_id, data = found_task
    print(f"✅ FOUND in tasks stream: {msg_id.decode()}")
    print(f"   Keys: {[k.decode() for k in data.keys()]}")
else:
    print(f"❌ Task NOT in last 100 messages of tasks stream")

# Check results stream
msgs = r.xrevrange(result_stream, count=100)
found_result = None
for msg_id, data in msgs:
    if target_task_id.encode() in str(data).encode():
        found_result = (msg_id, data)
        break

if found_result:
    msg_id, data = found_result
    print(f"✅ FOUND in results stream: {msg_id.decode()}")
else:
    print(f"❌ Task NOT in last 100 messages of results stream")

# Check consumer groups and pending
print()
print("Consumer groups:")
try:
    groups = r.xinfo_groups(stream)
    for g in groups:
        name = g.get(b'name', g.get('name', b'?'))
        if isinstance(name, bytes):
            name = name.decode()
        pending = g.get(b'pending', g.get('pending', 0))
        consumers = g.get(b'consumers', g.get('consumers', 0))
        print(f"  {name}: pending={pending}, consumers={consumers}")
except Exception as e:
    print(f"  Error: {e}")

# Show last 5 results to see what IS being processed
print()
print("Last 5 results (to see what IS being processed):")
msgs = r.xrevrange(result_stream, count=5)
for msg_id, data in msgs:
    try:
        meta = json.loads(data.get(b'metadata', b'{}'))
        payload = json.loads(data.get(b'payload', b'{}'))
        task_id = meta.get('task_id', '?')
        status = payload.get('status', '?')
        print(f"  {msg_id.decode()}: task={task_id[:50]}... status={status}")
    except Exception as e:
        print(f"  {msg_id.decode()}: parse error - {e}")

# Check if leads orchestrator is even enqueuing to persistence
print()
print("Checking leads orchestrator stream for compound writes...")
leads_results = r.xrevrange('agentic-dev:orchestrators:leads:results', count=5)
for msg_id, data in leads_results:
    try:
        payload = json.loads(data.get(b'payload', b'{}'))
        store = payload.get('store_inbound', {})
        if store:
            print(f"  {msg_id.decode()}: store_inbound={store}")
    except Exception as e:
        print(f"  {msg_id.decode()}: parse error")
