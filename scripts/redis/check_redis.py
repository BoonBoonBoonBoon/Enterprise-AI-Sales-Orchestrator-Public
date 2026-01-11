"""Quick Redis verification - check if setup worked"""
import os
import redis

os.environ.setdefault('REDIS_URL', os.getenv('REDIS_URL', 'redis://localhost:6379/0'))

r = redis.from_url(os.environ['REDIS_URL'], decode_responses=True)

# Check what streams exist
keys = r.keys('agentic-dev:*')
print(f"Found {len(keys)} streams:")
for key in sorted(keys)[:20]:
    length = r.xlen(key) if key.endswith(('tasks', 'results', 'dlq', 'health', 'audit', 'metrics', 'events')) else 'N/A'
    print(f"  {key}: {length}")
