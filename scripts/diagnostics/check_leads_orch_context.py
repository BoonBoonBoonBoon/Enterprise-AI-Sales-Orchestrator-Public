#!/usr/bin/env python
"""Check the Leads Orchestrator task and result to see lead_resolution context."""
import redis
import os
import json
from dotenv import load_dotenv
load_dotenv()

r = redis.Redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379'))

# Get all orchestrators:leads:tasks entries (latest 5)
print("=== LEADS ORCHESTRATOR TASKS (last 5) ===")
tasks = r.xrevrange('agentic-dev:orchestrators:leads:tasks', count=5)
for msg_id, data in tasks:
    d = json.loads(data.get(b'data', b'{}'))
    print(f"\nTask ID: {d.get('task_id')}")
    print(f"  msg_id: {msg_id.decode()}")
    payload = d.get('payload', {})
    print(f"  intent: {payload.get('intent')}")
    print(f"  email_from: {payload.get('email_event', {}).get('from')}")

print("\n\n=== LEADS ORCHESTRATOR RESULTS (last 5) ===")
results = r.xrevrange('agentic-dev:orchestrators:leads:results', count=5)
for msg_id, data in results:
    d = json.loads(data.get(b'data', b'{}'))
    print(f"\nTask ID: {d.get('task_id')}")
    print(f"  msg_id: {msg_id.decode()}")
    payload = d.get('payload', {})
    
    # Look for lead_resolution in various places
    store_inbound = payload.get('store_inbound', {})
    lead_ctx = payload.get('lead_context', {})
    rag_result = payload.get('rag_result', {})
    
    print(f"  store_inbound.stored: {store_inbound.get('stored')}")
    print(f"  store_inbound.status: {store_inbound.get('status')}")
    
    # Check for lead_resolution passed to the store function
    if 'lead_resolution' in str(payload):
        print(f"  FOUND lead_resolution in payload!")
    
    # Check lead_context which might contain the source
    if lead_ctx:
        print(f"  lead_context.lead_source: {lead_ctx.get('lead_source')}")
        print(f"  lead_context.lead_id: {lead_ctx.get('lead_id')}")
        print(f"  lead_context.query_trace: {lead_ctx.get('query_trace', {}).get('steps')}")
    
    # Check rag_result
    if rag_result:
        print(f"  rag_result: {json.dumps(rag_result, indent=4)[:500]}")
