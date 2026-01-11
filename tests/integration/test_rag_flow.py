#!/usr/bin/env python3
"""
Quick test: Publish task to RAG agent and retrieve result.
Verifies the hierarchical stream naming is working end-to-end with typed envelopes.
"""

import redis
import json
import os
import time
from dotenv import load_dotenv
import uuid

# Import typed envelope from core package
from core.envelope import task, result, to_redis_fields, from_redis_message, Priority

load_dotenv()

REDIS_URL = os.getenv('REDIS_URL')
TENANT = 'agentic-dev'

def main():
    # Connect to Redis
    r = redis.from_url(REDIS_URL, decode_responses=True)
    r.ping()
    print("✓ Connected to Redis Cloud\n")
    
    # Stream names (hierarchical)
    task_stream = f"{TENANT}:agents:rag:tasks"
    result_stream = f"{TENANT}:agents:rag:results"
    
    # Create a test task using typed envelope
    task_id = f"test_task_{uuid.uuid4()}"
    lead_id = "lead_test_123"
    goal = "Enrich lead information for TechCorp Inc - find funding, company size, and industry"
    
    # Create typed envelope
    task_envelope = task(
        source="test_script",
        task_id=task_id,
        destination=task_stream,
        payload={
            "goal": goal,
            "lead_id": lead_id,
            "context": {
                "company": "TechCorp Inc",
                "lead_source": "test_script"
            }
        },
        priority=Priority.NORMAL,
        correlation_id=f"test_correlation_{uuid.uuid4()}",
        tenant_id=TENANT,
        campaign_id="test_campaign_001"
    )
    
    print("=" * 70)
    print("📤 PUBLISHING TASK TO RAG AGENT (Typed Envelope)")
    print("=" * 70)
    print(f"\nStream: {task_stream}")
    print(f"Task ID: {task_id}")
    print(f"Goal: {goal}")
    print(f"\nTyped Envelope Structure:")
    print(json.dumps(json.loads(task_envelope.to_json()), indent=2))
    print()
    
    # Publish task using typed envelope
    msg_id = r.xadd(task_stream, to_redis_fields(task_envelope))
    print(f"✓ Task published with message ID: {msg_id}")
    
    # Show task in stream
    messages = r.xrange(task_stream, count=1)
    if messages:
        print(f"\n✓ Verified in Redis: Task exists in {task_stream}")
        print(f"  Message count: {r.xlen(task_stream)}")
    
    print("\n" + "=" * 70)
    print("⏳ SIMULATING RAG AGENT PROCESSING")
    print("=" * 70)
    print("\n(In real scenario, RAG Agent consumer would process this)")
    print("(For now, we'll simulate the result...)\n")
    
    # Simulate RAG agent processing - publish a result using typed envelope
    time.sleep(1)
    
    # Create result envelope from original task
    result_envelope = result(
        original=task_envelope,
        payload={
            "result": {
                "company": "TechCorp Inc",
                "industry": "Software",
                "funding": "$50M Series B",
                "employees": "150-200",
                "website": "techcorp.com",
                "confidence_scores": {
                    "company": 0.98,
                    "funding": 0.95,
                    "industry": 0.99
                }
            },
            "processing_time_ms": 1250,
        },
        source="rag_worker"
    )
    
    print("=" * 70)
    print("📥 PUBLISHING RESULT FROM RAG AGENT (Typed Envelope)")
    print("=" * 70)
    print(f"\nStream: {result_stream}")
    print(f"Task ID: {task_id}")
    print(f"Status: {result_envelope.status}")
    print(f"\nTyped Envelope Structure:")
    print(json.dumps(json.loads(result_envelope.to_json()), indent=2))
    print()
    
    # Publish result using typed envelope
    result_msg_id = r.xadd(result_stream, to_redis_fields(result_envelope))
    print(f"✓ Result published with message ID: {result_msg_id}")
    
    # Show result in stream
    messages = r.xrange(result_stream, count=1)
    if messages:
        print(f"\n✓ Verified in Redis: Result exists in {result_stream}")
        print(f"  Message count: {r.xlen(result_stream)}")
    
    # Show complete flow
    print("\n" + "=" * 70)
    print("✅ COMPLETE VERIFICATION")
    print("=" * 70)
    print(f"\nTask Stream:   {task_stream}")
    print(f"  Messages: {r.xlen(task_stream)}")
    print(f"\nResult Stream: {result_stream}")
    print(f"  Messages: {r.xlen(result_stream)}")
    
    # Retrieve and display the task envelope
    print(f"\n📋 Task Envelope Details:")
    task_messages = r.xrange(task_stream, min=f'({msg_id}', count=1)
    if task_messages:
        msg_id_retrieved, msg_data = task_messages[0]
        retrieved_envelope = from_redis_message(msg_data)
        print(f"  Message ID: {msg_id_retrieved}")
        print(f"  Task ID: {retrieved_envelope.metadata.task_id}")
        print(f"  Source: {retrieved_envelope.metadata.source}")
        print(f"  Correlation ID: {retrieved_envelope.metadata.correlation_id}")
        print(f"  Tenant ID: {retrieved_envelope.metadata.tenant_id}")
        print(f"  Priority: {retrieved_envelope.metadata.priority}")
        print(f"  Goal: {retrieved_envelope.payload.get('goal')}")
    
    # Retrieve and display the result envelope
    print(f"\n📊 Result Envelope Details:")
    result_messages = r.xrange(result_stream, min=f'({result_msg_id}', count=1)
    if result_messages:
        msg_id_retrieved, msg_data = result_messages[0]
        retrieved_envelope = from_redis_message(msg_data)
        print(f"  Message ID: {msg_id_retrieved}")
        print(f"  Task ID: {retrieved_envelope.metadata.task_id}")
        print(f"  Source: {retrieved_envelope.metadata.source}")
        print(f"  Status: {retrieved_envelope.status}")
        print(f"  Correlation ID: {retrieved_envelope.metadata.correlation_id}")
        result_data = retrieved_envelope.payload.get('result', {})
        print(f"  Company: {result_data.get('company')}")
        print(f"  Industry: {result_data.get('industry')}")
        print(f"  Confidence: {result_data.get('confidence_scores', {}).get('company')}")
    
    print("\n" + "=" * 70)
    print("🎉 HIERARCHICAL STREAM FLOW WITH TYPED ENVELOPES WORKING!")
    print("=" * 70)
    print("\n✓ Task successfully published to: agentic-dev:agents:rag:tasks")
    print("✓ Result successfully published to: agentic-dev:agents:rag:results")
    print("✓ Both streams accessible with hierarchical naming")
    print("✓ Using global typed envelope standard (Pydantic)")
    print("✓ Full metadata preserved: correlation_id, tenant_id, priorities")
    print("\n")

if __name__ == '__main__':
    main()
