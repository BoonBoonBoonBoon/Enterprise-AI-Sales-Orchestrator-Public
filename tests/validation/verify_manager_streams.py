"""Verify manager streams exist in Redis"""
import redis
import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Connect to Redis - use REDIS_URL from env if available, else localhost
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
print(f"Connecting to: {redis_url.split('@')[-1] if '@' in redis_url else redis_url}\n")
r = redis.Redis.from_url(redis_url, decode_responses=False)

print("Checking Redis for manager streams...")
print("=" * 60)

# Check for manager streams
task_stream = "agentic-dev:manager:tasks"
result_stream = "agentic-dev:manager:results"

print(f"\n1. Checking {task_stream}...")
try:
    task_len = r.xlen(task_stream)
    print(f"   ✓ Stream exists with {task_len} messages")
    
    if task_len > 0:
        # Read first message
        messages = r.xread({task_stream: '0'}, count=1)
        if messages:
            print(f"   Sample message ID: {messages[0][1][0][0].decode()}")
except Exception as e:
    print(f"   ✗ Error: {e}")

print(f"\n2. Checking {result_stream}...")
try:
    result_len = r.xlen(result_stream)
    print(f"   ✓ Stream exists with {result_len} messages")
except Exception as e:
    print(f"   ✗ Error: {e}")

# List all agentic-dev:manager:* keys
print("\n3. All manager-related keys:")
try:
    keys = r.keys("agentic-dev:manager:*")
    if keys:
        for key in keys:
            key_str = key.decode() if isinstance(key, bytes) else key
            key_type = r.type(key).decode() if isinstance(r.type(key), bytes) else r.type(key)
            print(f"   - {key_str} (type: {key_type})")
    else:
        print("   No keys found")
except Exception as e:
    print(f"   ✗ Error: {e}")

# Check Redis info
print("\n4. Redis Info:")
info = r.info()
print(f"   Redis version: {info['redis_version']}")
print(f"   Used memory: {info['used_memory_human']}")
print(f"   Connected clients: {info['connected_clients']}")

print("\n" + "=" * 60)
print("Verification complete!")
