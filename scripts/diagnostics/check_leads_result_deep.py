#!/usr/bin/env python
"""Deep check of the specific leads orchestrator result."""
import redis
import os
import json
from dotenv import load_dotenv
load_dotenv()

r = redis.Redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379'))

msg = r.xrange('agentic-dev:orchestrators:leads:results', min='1767893742683-0', max='1767893742683-0')
if msg:
    msg_id, data = msg[0]
    d = json.loads(data.get(b'data', b'{}'))
    payload = d.get('payload', {})
    
    print("=== FULL LEADS ORCHESTRATOR RESULT ===")
    print(json.dumps(payload, indent=2, default=str))
