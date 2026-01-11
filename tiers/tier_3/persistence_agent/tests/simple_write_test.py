"""
Simple standalone test for Persistence Agent write operations.
Run with: python tiers/tier_3/persistence_agent/tests/simple_write_test.py
"""

import asyncio
import os
import uuid
import json
from datetime import datetime
from dotenv import load_dotenv
import redis.asyncio as aioredis

# Load environment
load_dotenv()

async def send_task(redis_client, tenant_id, task_id, goal, context):
    """Send a task to Persistence Agent."""
    task_stream = f"{tenant_id}:agents:persistence:tasks"
    
    # Create Redis fields
    redis_fields = {
        "task_id": task_id,
        "tenant_id": tenant_id,
        "payload": json.dumps({"goal": goal, "context": context}),
        "metadata": json.dumps({
            "source": "simple_test",
            "target": "persistence",
            "timestamp": datetime.now().isoformat()
        })
    }
    
    # Publish
    await redis_client.xadd(task_stream, redis_fields)
    print(f"📤 Published task {task_id}")
    return task_id

async def wait_for_result(redis_client, tenant_id, task_id, timeout=30):
    """Wait for result from Persistence Agent."""
    result_stream = f"{tenant_id}:agents:persistence:results"
    start_time = datetime.now()
    
    while (datetime.now() - start_time).total_seconds() < timeout:
        results = await redis_client.xread(
            {result_stream: "0"},
            count=100,
            block=1000
        )
        
        if results:
            for stream, messages in results:
                for message_id, data in messages:
                    if data.get("task_id") == task_id:
                        print(f"✅ Received result for task {task_id}")
                        # Parse payload if JSON
                        result_data = dict(data)
                        if "payload" in result_data and isinstance(result_data["payload"], str):
                            try:
                                result_data["payload"] = json.loads(result_data["payload"])
                            except:
                                pass
                        return result_data.get("payload", result_data)
        
        await asyncio.sleep(0.5)
    
    print(f"⏱️ Timeout waiting for result")
    return None

async def test_create_staging_lead():
    """Test creating a single staging lead."""
    print("\n" + "="*60)
    print("TEST: Create Staging Lead")
    print("="*60)
    
    # Connect to Redis
    redis_url = os.getenv("REDIS_URL")
    redis_client = aioredis.from_url(redis_url, decode_responses=True)
    
    try:
        # Test data
        tenant_id = "agentic-dev"
        task_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Send task
        await send_task(
            redis_client=redis_client,
            tenant_id=tenant_id,
            task_id=task_id,
            goal=f"Create staging lead for simple_test_{timestamp}@example.com",
            context={
                "email": f"simple_test_{timestamp}@example.com",
                "first_name": "Test",
                "last_name": "User",
                "company": "Test Company",
                "title": "Tester",
                "source": "simple_test",
                "client_id": str(uuid.uuid4())
            }
        )
        
        # Wait for result
        result = await wait_for_result(redis_client, tenant_id, task_id)
        
        if result:
            print(f"\n📊 Result: {json.dumps(result, indent=2)}")
            if result.get("status") == "success":
                print(f"\n✅ SUCCESS: Created staging lead with ID {result.get('id')}")
            else:
                print(f"\n❌ FAILED: {result}")
        else:
            print(f"\n❌ FAILED: No result received")
    
    finally:
        await redis_client.aclose()

if __name__ == "__main__":
    asyncio.run(test_create_staging_lead())
