"""Quick status check for Redis streams and recent results.

Note: Stream names follow the hierarchical convention:
- {tenant}:manager:*
- {tenant}:orchestrators:{name}:*
- {tenant}:agents:{name}:*
"""

import json
import os

import redis
from dotenv import load_dotenv


load_dotenv()

redis_url = os.getenv("REDIS_URL")
if not redis_url:
    raise SystemExit("REDIS_URL is not set; cannot query Redis.")

client = redis.from_url(redis_url, decode_responses=True)
tenant = os.getenv("TENANT_ID", "agentic-dev")

# 1. Check latest RAG result payload
print('=== LATEST RAG RESULT ===')
latest = client.xrevrange(f'{tenant}:agents:rag:results', count=1)
if latest:
    msg_id, data = latest[0]
    print(f'Message ID: {msg_id}')
    for k, v in data.items():
        if k == 'payload':
            try:
                payload = json.loads(v) if isinstance(v, str) else v
                print(f'Payload: {json.dumps(payload, indent=2)[:1000]}')
            except:
                print(f'Payload: {str(v)[:500]}')
        elif k == 'metadata':
            try:
                meta = json.loads(v) if isinstance(v, str) else v
                print(f'Metadata: task_id={meta.get("task_id", "N/A")}, source={meta.get("source", "N/A")}')
            except:
                print(f'Metadata: {str(v)[:200]}')
        else:
            print(f'{k}: {str(v)[:100]}')

# 2. Pending messages (read-only)
print()
print('=== RAG PENDING (READ-ONLY) ===')
stream = f'{tenant}:agents:rag:tasks'
group = 'rag-workers'
try:
    pending = client.xpending_range(stream, group, '-', '+', count=50)
    print(f'Found {len(pending)} pending messages')
    for p in pending[:10]:
        print(f"  {p.get('message_id')} consumer={p.get('consumer')} idle={p.get('time_since_delivered')}ms")
except Exception as exc:
    print(f'Could not query pending for {stream} ({group}): {exc}')

# 3. Current stream status
print()
print('=== STREAM STATUS ===')
streams = [
    f'{tenant}:manager:tasks',
    f'{tenant}:manager:results',
    f'{tenant}:orchestrators:leads:tasks',
    f'{tenant}:orchestrators:leads:results',
    f'{tenant}:orchestrators:outbound:tasks',
    f'{tenant}:orchestrators:outbound:results',
    f'{tenant}:agents:rag:tasks',
    f'{tenant}:agents:rag:results',
]
for s in streams:
    name = s
    count = client.xlen(s)
    print(f'  {name}: {count}')
