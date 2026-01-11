"""
Test script for Persistence and Copywriter agents with hierarchical streams.

Tests:
1. Persistence Agent - write operation
2. Copywriter Agent - email generation
3. End-to-end delegation flow
"""

import asyncio
import redis.asyncio as redis
import json
from datetime import datetime, UTC
import os
import pytest
from core.envelope import task, result, from_redis_message, to_redis_fields


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_AGENTS") != "1",
    reason="Requires live Persistence/Copywriter consumers running (set RUN_LIVE_AGENTS=1)",
)

# Configuration
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_PASSWORD = None
TENANT_ID = "agentic-dev"

# Hierarchical stream names
PERSISTENCE_TASK_STREAM = f"{TENANT_ID}:agents:persistence:tasks"
PERSISTENCE_RESULT_STREAM = f"{TENANT_ID}:agents:persistence:results"
COPYWRITER_TASK_STREAM = f"{TENANT_ID}:agents:copywriter:tasks"
COPYWRITER_RESULT_STREAM = f"{TENANT_ID}:agents:copywriter:results"


async def verify_streams(redis_client: redis.Redis):
    """Verify all streams exist with correct hierarchical naming."""
    print("\n" + "="*80)
    print("STREAM VERIFICATION")
    print("="*80)
    
    streams = [
        PERSISTENCE_TASK_STREAM,
        PERSISTENCE_RESULT_STREAM,
        COPYWRITER_TASK_STREAM,
        COPYWRITER_RESULT_STREAM
    ]
    
    for stream in streams:
        try:
            info = await redis_client.xinfo_stream(stream)
            length = info.get("length", 0)
            print(f"✓ {stream}")
            print(f"  Length: {length} messages")
        except redis.ResponseError:
            print(f"⚠ {stream} (does not exist yet)")


async def test_persistence_write(redis_client: redis.Redis):
    """Test Persistence Agent write operation."""
    print("\n" + "="*80)
    print("TEST 1: Persistence Agent - Single Write")
    print("="*80)
    
    # Create task envelope
    task_envelope = task(
        task_id=f"persist_write_{datetime.now(UTC).timestamp()}",
        source="test_script",
        destination="agents:persistence",
        payload={
            "goal": "Write a new lead record to the database",
            "operation": "write",
            "table": "leads",
            "record": {
                "company_name": "Test Company Inc",
                "contact_name": "John Doe",
                "email": "john@testcompany.com",
                "status": "new"
            }
        },
        tenant_id=TENANT_ID
    )
    
    # Publish to task stream
    message_id = await redis_client.xadd(
        PERSISTENCE_TASK_STREAM,
        to_redis_fields(task_envelope)
    )
    
    print(f"✓ Published task to {PERSISTENCE_TASK_STREAM}")
    print(f"  Message ID: {message_id}")
    print(f"  Task ID: {task_envelope.metadata.task_id}")
    print(f"  Payload: {json.dumps(task_envelope.payload, indent=2)}")
    
    # Wait for result
    print("\n⏳ Waiting for result...")
    await asyncio.sleep(2)
    
    # Read result
    messages = await redis_client.xread(
        {PERSISTENCE_RESULT_STREAM: "0"},
        count=10
    )
    
    if messages:
        print(f"\n✓ Found {len(messages[0][1])} message(s) in result stream")
        for msg_id, msg_data in messages[0][1]:
            envelope = from_redis_message(msg_data)
            if envelope.metadata.task_id == task_envelope.metadata.task_id:
                print(f"\n✅ Found matching result!")
                print(f"  Status: {envelope.status}")
                print(f"  Payload: {json.dumps(envelope.payload, indent=2)}")
                return True
    
    print("❌ No result found")
    return False


async def test_copywriter_email(redis_client: redis.Redis):
    """Test Copywriter Agent email generation."""
    print("\n" + "="*80)
    print("TEST 2: Copywriter Agent - Email Generation")
    print("="*80)
    
    # Create task envelope
    task_envelope = task(
        task_id=f"copy_email_{datetime.now(UTC).timestamp()}",
        source="test_script",
        destination="agents:copywriter",
        payload={
            "goal": "Generate a professional outreach email",
            "type": "email",
            "context": {
                "recipient_name": "Sarah Johnson",
                "company_name": "TechCorp Inc",
                "value_prop": "AI-powered lead generation platform",
                "call_to_action": "Schedule a 15-minute demo call",
                "additional_context": "They recently raised Series A funding"
            },
            "tone": "professional",
            "length": "medium"
        },
        tenant_id=TENANT_ID
    )
    
    # Publish to task stream
    message_id = await redis_client.xadd(
        COPYWRITER_TASK_STREAM,
        to_redis_fields(task_envelope)
    )
    
    print(f"✓ Published task to {COPYWRITER_TASK_STREAM}")
    print(f"  Message ID: {message_id}")
    print(f"  Task ID: {task_envelope.metadata.task_id}")
    print(f"  Recipient: {task_envelope.payload['context']['recipient_name']}")
    
    # Wait for result
    print("\n⏳ Waiting for result...")
    await asyncio.sleep(2)
    
    # Read result
    messages = await redis_client.xread(
        {COPYWRITER_RESULT_STREAM: "0"},
        count=10
    )

    if messages:
        for msg_id, msg_data in messages[0][1]:
            try:
                envelope = from_redis_message(msg_data)
            except Exception:
                # Skip legacy/malformed entries that lack envelope metadata
                continue

            if envelope.metadata.task_id == task_envelope.metadata.task_id:
                print(f"\n✅ Found matching result!")
                print(f"  Status: {envelope.status}")
                copy = envelope.payload.get("copy", {})
                if isinstance(copy, dict):
                    print(f"\n  Subject: {copy.get('subject', 'N/A')}")
                    print(f"  Body: {copy.get('body', 'N/A')[:200]}...")
                return True
    
    print("❌ No result found")
    return False


async def test_copywriter_sms(redis_client: redis.Redis):
    """Test Copywriter Agent SMS generation."""
    print("\n" + "="*80)
    print("TEST 3: Copywriter Agent - SMS Generation")
    print("="*80)
    
    # Create task envelope
    task_envelope = task(
        task_id=f"copy_sms_{datetime.now(UTC).timestamp()}",
        source="test_script",
        destination="agents:copywriter",
        payload={
            "goal": "Generate a promotional SMS message",
            "type": "sms",
            "context": {
                "recipient_name": "Mike",
                "company_name": "AgenticAI",
                "message_type": "promo",
                "key_info": "Limited time offer: 50% off first month"
            },
            "tone": "friendly",
            "max_length": 160
        },
        tenant_id=TENANT_ID
    )
    
    # Publish to task stream
    message_id = await redis_client.xadd(
        COPYWRITER_TASK_STREAM,
        to_redis_fields(task_envelope)
    )
    
    print(f"✓ Published task to {COPYWRITER_TASK_STREAM}")
    print(f"  Message ID: {message_id}")
    print(f"  Task ID: {task_envelope.metadata.task_id}")
    print(f"  Max Length: {task_envelope.payload['max_length']} chars")
    
    # Wait for result
    print("\n⏳ Waiting for result...")
    await asyncio.sleep(2)
    
    # Read result
    messages = await redis_client.xread(
        {COPYWRITER_RESULT_STREAM: "0"},
        count=10
    )

    if messages:
        for msg_id, msg_data in messages[0][1]:
            try:
                envelope = from_redis_message(msg_data)
            except Exception:
                # Skip legacy/malformed entries that lack envelope metadata
                continue

            if envelope.metadata.task_id == task_envelope.metadata.task_id:
                print(f"\n✅ Found matching result!")
                print(f"  Status: {envelope.status}")
                copy = envelope.payload.get("copy", {})
                if isinstance(copy, dict):
                    text = copy.get('text', 'N/A')
                    print(f"\n  Text: {text}")
                    print(f"  Length: {len(text)} chars")
                return True
    
    print("❌ No result found")
    return False


async def main():
    """Main test runner."""
    print("\n" + "="*80)
    print("PERSISTENCE & COPYWRITER AGENTS TEST SUITE")
    print("="*80)
    print(f"Redis: {REDIS_HOST}:{REDIS_PORT}")
    print(f"Tenant: {TENANT_ID}")
    
    # Initialize Redis client
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        decode_responses=False
    )
    
    try:
        # Test connection
        await redis_client.ping()
        print("✓ Connected to Redis")
        
        # Verify streams
        await verify_streams(redis_client)
        
        # Run tests
        results = {
            "Persistence Write": await test_persistence_write(redis_client),
            "Copywriter Email": await test_copywriter_email(redis_client),
            "Copywriter SMS": await test_copywriter_sms(redis_client)
        }
        
        # Summary
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        
        passed = sum(1 for v in results.values() if v)
        total = len(results)
        
        for test_name, passed_test in results.items():
            status = "✅ PASS" if passed_test else "❌ FAIL"
            print(f"{status} - {test_name}")
        
        print(f"\n{passed}/{total} tests passed")
        
        if passed == total:
            print("\n🎉 All tests passed!")
        else:
            print(f"\n⚠️ {total - passed} test(s) failed")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
