#!/usr/bin/env python
"""Check the RAG agent task and result."""
import redis
import os
import json
from dotenv import load_dotenv
load_dotenv()

r = redis.Redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379'))

# Look for RAG task around the same time (1767893722218 is the persistence task timestamp)
print("=== RAG AGENT RESULTS (last 10) ===")
results = r.xrevrange('agentic-dev:agents:rag:results', count=10)
for msg_id, data in results:
    d = json.loads(data.get(b'data', b'{}'))
    task_id = d.get('task_id', d.get('metadata', {}).get('task_id'))
    payload = d.get('payload', {})
    
    if 'rag_ctx' in str(task_id):
        print(f"\n=== {msg_id.decode()} ===")
        print(f"Task ID: {task_id}")
        print(f"Status: {payload.get('status')}")
        print(f"lead_source: {payload.get('lead_source')}")
        print(f"lead: {payload.get('lead')}")
        print()
