"""
Send a test event to manager:tasks stream that you can easily see in RedisInsight
"""
import redis
import json
import uuid
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Connect to Redis - use REDIS_URL from env if available, else localhost
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
print(f"Connecting to: {redis_url.split('@')[-1] if '@' in redis_url else redis_url}")
r = redis.Redis.from_url(redis_url, decode_responses=False)

print("Sending test event to manager:tasks...")
print("=" * 60)

# Create a test task
task_id = str(uuid.uuid4())
task_data = {
    "task_id": task_id,
    "task": "🔥 TEST EVENT - You should see this in RedisInsight! 🔥",
    "orchestrator": "coding",
    "priority": "urgent",
    "tenant_id": "agentic-dev",
    "timestamp": datetime.now().isoformat(),
    "test": True,
    "message": "If you see this, the manager streams are working correctly!"
}

# Send to stream
stream_id = r.xadd(
    "agentic-dev:manager:tasks",
    {
        "payload": json.dumps(task_data),
        "task_id": task_id,
        "priority": "urgent",
        "orchestrator": "coding",
        "test": "true"
    }
)

print(f"✓ Test event sent!")
print(f"  Task ID: {task_id}")
print(f"  Stream ID: {stream_id.decode()}")
print(f"  Stream: agentic-dev:manager:tasks")

# Verify it's there
total = r.xlen("agentic-dev:manager:tasks")
print(f"\n✓ Stream now has {total} messages")

# Read the last message
messages = r.xrevrange("agentic-dev:manager:tasks", count=1)
if messages:
    msg_id, msg_data = messages[0]
    print(f"\n✓ Last message in stream:")
    print(f"  ID: {msg_id.decode()}")
    payload = json.loads(msg_data[b'payload'].decode())
    print(f"  Task: {payload['task']}")

print("\n" + "=" * 60)
print("Now check RedisInsight:")
print("1. Click the refresh button (circular arrow)")
print("2. Look for 'agentic-dev' folder")
print("3. Expand it to see 'manager' folder")
print("4. Click on 'tasks' stream")
print("5. You should see the test event with the fire emoji!")
print("\nIf you still don't see it, you might be connected to a different Redis instance.")
print("Check RedisInsight connection settings (host, port, database number).")
