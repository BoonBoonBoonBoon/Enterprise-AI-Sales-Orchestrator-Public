#!/usr/bin/env python
"""Check the actual persistence task payload."""
import redis
import os
import json
from dotenv import load_dotenv
load_dotenv()

r = redis.Redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379'))

msg = r.xrange('agentic-dev:agents:persistence:tasks', min='1767893722218-0', max='1767893722218-0')
if msg:
    msg_id, data = msg[0]
    d = json.loads(data.get(b'data', b'{}'))
    print("=== FULL PERSISTENCE TASK ===")
    print(json.dumps(d, indent=2, default=str))
