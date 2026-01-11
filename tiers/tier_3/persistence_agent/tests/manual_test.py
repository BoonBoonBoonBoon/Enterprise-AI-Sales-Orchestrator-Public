"""
Direct test - manually add task and check results.
"""
import redis
import os
import json
import uuid
from datetime import datetime
from dotenv import load_dotenv
import time

load_dotenv()

def main():
    # Connect to Redis
    redis_url = os.getenv("REDIS_URL")
    r = redis.from_url(redis_url, decode_responses=True)
    
    tenant_id = "agentic-dev"
    task_id = str(uuid.uuid4())
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    print(f"\n{'='*60}")
    print(f"MANUAL WRITE TEST")
    print(f"{'='*60}")
    print(f"Task ID: {task_id}")
    print(f"Timestamp: {timestamp}")
    
    # Create task
    task_stream = f"{tenant_id}:agents:persistence:tasks"
    result_stream = f"{tenant_id}:agents:persistence:results"
    
    redis_fields = {
        "task_id": task_id,
        "tenant_id": tenant_id,
        "payload": json.dumps({
            "goal": f"Create staging lead for manual_test_{timestamp}@example.com",
            "context": {
                "email": f"manual_test_{timestamp}@example.com",
                "first_name": "Manual",
                "last_name": "Test",
                "company": "Test Co",
                "title": "Tester",
                "source": "manual_script",
                "client_id": str(uuid.uuid4())
            }
        }),
        "metadata": json.dumps({
            "source": "manual_test",
            "target": "persistence",
            "timestamp": datetime.now().isoformat()
        })
    }
    
    # Add to stream
    message_id = r.xadd(task_stream, redis_fields)
    print(f"\n✅ Added task to stream: {message_id}")
    
    # Wait and check for result
    print(f"\n⏳ Waiting for result (30 seconds)...")
    for i in range(30):
        # Read recent results
        results = r.xrevrange(result_stream, count=10)
        for mid, data in results:
            if data.get("task_id") == task_id:
                print(f"\n✅ FOUND RESULT!")
                print(f"Message ID: {mid}")
                print(f"Data: {json.dumps(data, indent=2)}")
                return
        
        time.sleep(1)
        if (i + 1) % 5 == 0:
            print(f"  ... {i + 1}s elapsed")
    
    print(f"\n❌ Timeout - no result found")
    print(f"\nLast 3 results in stream:")
    results = r.xrevrange(result_stream, count=3)
    for mid, data in results:
        print(f"  {mid}: task_id={data.get('task_id')}")

if __name__ == "__main__":
    main()
