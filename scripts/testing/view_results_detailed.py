import redis
import json
import os
from dotenv import load_dotenv

load_dotenv()

redis_url = os.getenv('REDIS_URL')
r = redis.from_url(redis_url, decode_responses=True)

print('Last 3 Detailed Results:')
print('='*70)

results = r.xrevrange('agentic-dev:agents:rag:results', count=3)
for i, (msg_id, data) in enumerate(results, 1):
    print(f'\nResult {i}: {msg_id}')
    print('-'*70)
    
    # The 'data' dict should have 'payload' as raw string
    if 'data' in data:
        # Sometimes the key is 'data' instead of 'payload'
        raw_payload = data.get('data') or data.get('payload')
    else:
        raw_payload = data.get('payload')
    
    if raw_payload:
        try:
            payload_obj = json.loads(raw_payload)
            print(json.dumps(payload_obj, indent=2)[:1000])
        except:
            print(raw_payload[:500])
    else:
        print('Payload fields:', list(data.keys()))
