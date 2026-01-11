"""
Manual E2E Test - LeadsOrchestrator Delegation Flow

Tests the complete flow:
1. Send task to LeadsOrchestrator
2. Orchestrator makes decision and delegates to T3 agents
3. T3 agents process and return results
4. Orchestrator aggregates and returns final result

This follows the correct Redis Streams architecture.
"""

import asyncio
import json
from services.redis.client import RedisStreamsClient
from core.envelope import task, to_redis_fields, from_redis_message
import time


async def test_enrichment_delegation():
    """Test LeadsOrchestrator delegating enrichment to RAG Agent"""
    print("\n" + "="*80)
    print("TEST: LeadsOrchestrator → RAG Agent Delegation (Enrichment)")
    print("="*80 + "\n")
    
    tenant_id = "agentic-dev"
    # Don't pass namespace - let RedisStreamsClient use default "agentic" 
    # Then consumers see: agentic:agentic-dev:orchestrators:leads:tasks
    redis_client = RedisStreamsClient(url="redis://localhost:6379")  # Uses default "agentic" namespace
    
    # Task for LeadsOrchestrator
    orchestrator_stream = f"{tenant_id}:orchestrators:leads:tasks"
    rag_stream = f"{tenant_id}:agents:rag:tasks"
    
    # Create enrichment task (should delegate to RAG)
    envelope = task(
        source="manual_test",
        task_id=f"test-enrichment-{int(time.time())}",
        payload={
            "operation": "enrich",
            "lead": {
                "name": "Acme Corp",
                "domain": "acme.com",
                "email": "contact@acme.com"
            }
        },
        destination="leads_orchestrator",
        tenant_id=tenant_id
    )
    
    print(f"📤 Sending enrichment task to: {orchestrator_stream}")
    print(f"   Task ID: {envelope.metadata.task_id}")
    print(f"   Operation: enrich")
    print(f"   Expected: LeadsOrchestrator should delegate to RAG")
    
    # Send to orchestrator
    msg_id = redis_client.xadd(orchestrator_stream, to_redis_fields(envelope))
    print(f"✅ Message sent: {msg_id}\n")
    
    # Wait and check if RAG received delegation
    print(f"⏳ Waiting 10s for orchestrator to delegate to RAG...")
    await asyncio.sleep(10)
    
    # Check RAG stream
    rag_length = redis_client.client.xlen(rag_stream)
    print(f"\n📊 RAG stream length: {rag_length}")
    
    if rag_length > 0:
        # Read last message from RAG stream
        messages = redis_client.xread({rag_stream: "0"}, count=10)
        if messages:
            print(f"✅ RAG Agent received delegation!")
            for stream_name, stream_messages in messages:
                for msg_id, msg_data in stream_messages[-1:]:  # Last message
                    env = from_redis_message(msg_data)
                    print(f"\n📦 Delegated Task to RAG:")
                    print(f"   Task ID: {env.metadata.task_id}")
                    print(f"   Payload: {json.dumps(env.payload, indent=2)}")
    else:
        print(f"❌ No delegation to RAG detected")
        print(f"💡 Check if LeadsOrchestrator consumer is running")
    
    return rag_length > 0


async def test_bulk_delegation():
    """Test LeadsOrchestrator delegating bulk operations to Persistence Agent"""
    print("\n" + "="*80)
    print("TEST: LeadsOrchestrator → Persistence Agent Delegation (Bulk Import)")
    print("="*80 + "\n")
    
    tenant_id = "agentic-dev"
    redis_client = RedisStreamsClient(url="redis://localhost:6379")  # Uses default "agentic" namespace
    
    orchestrator_stream = f"{tenant_id}:orchestrators:leads:tasks"
    persistence_stream = f"{tenant_id}:agents:persistence:tasks"
    
    # Create bulk import task (should delegate to Persistence for 100+ leads)
    bulk_leads = [
        {"name": f"Company {i}", "email": f"contact{i}@company{i}.com"}
        for i in range(150)  # 150 leads = bulk operation
    ]
    
    envelope = task(
        source="manual_test",
        task_id=f"test-bulk-{int(time.time())}",
        payload={
            "operation": "bulk_import",
            "leads": bulk_leads
        },
        destination="leads_orchestrator",
        tenant_id=tenant_id
    )
    
    print(f"📤 Sending bulk import task to: {orchestrator_stream}")
    print(f"   Task ID: {envelope.metadata.task_id}")
    print(f"   Operation: bulk_import")
    print(f"   Lead count: {len(bulk_leads)}")
    print(f"   Expected: LeadsOrchestrator should delegate to Persistence")
    
    msg_id = redis_client.xadd(orchestrator_stream, to_redis_fields(envelope))
    print(f"✅ Message sent: {msg_id}\n")
    
    print(f"⏳ Waiting 10s for orchestrator to delegate to Persistence...")
    await asyncio.sleep(10)
    
    # Check Persistence stream
    persistence_length = redis_client.client.xlen(persistence_stream)
    print(f"\n📊 Persistence stream length: {persistence_length}")
    
    if persistence_length > 0:
        messages = redis_client.xread({persistence_stream: "0"}, count=10)
        if messages:
            print(f"✅ Persistence Agent received delegation!")
            for stream_name, stream_messages in messages:
                for msg_id, msg_data in stream_messages[-1:]:
                    env = from_redis_message(msg_data)
                    print(f"\n📦 Delegated Task to Persistence:")
                    print(f"   Task ID: {env.metadata.task_id}")
                    lead_count = len(env.payload.get('leads', []))
                    print(f"   Lead count: {lead_count}")
    else:
        print(f"❌ No delegation to Persistence detected")
        print(f"💡 Check if LeadsOrchestrator consumer is running")
    
    return persistence_length > 0


async def check_redis_state():
    """Check current Redis state"""
    print("\n" + "="*80)
    print("REDIS STATE CHECK")
    print("="*80 + "\n")
    
    tenant_id = "agentic-dev"
    redis_client = RedisStreamsClient(url="redis://localhost:6379")  # Uses default "agentic" namespace
    
    streams_to_check = [
        f"{tenant_id}:orchestrators:leads:tasks",
        f"{tenant_id}:orchestrators:leads:results",
        f"{tenant_id}:agents:rag:tasks",
        f"{tenant_id}:agents:rag:results",
        f"{tenant_id}:agents:persistence:tasks",
        f"{tenant_id}:agents:persistence:results",
    ]
    
    print("Stream Lengths:")
    for stream in streams_to_check:
        try:
            length = redis_client.client.xlen(stream)
            stream_name = stream.split(":")[-2] + ":" + stream.split(":")[-1]
            if length > 0:
                print(f"  ✅ {stream_name:30s} {length} messages")
            else:
                print(f"  ⚪ {stream_name:30s} (empty)")
        except Exception:
            stream_name = stream.split(":")[-2] + ":" + stream.split(":")[-1]
            print(f"  ❌ {stream_name:30s} (not created)")
    
    # Check consumer groups
    print("\nConsumer Groups:")
    group_checks = [
        (f"{tenant_id}:orchestrators:leads:tasks", "leads-workers"),
        (f"{tenant_id}:agents:rag:tasks", "rag-workers"),
        (f"{tenant_id}:agents:persistence:tasks", "persistence-workers"),
    ]
    
    for stream, expected_group in group_checks:
        try:
            groups = redis_client.client.xinfo_groups(stream)
            group_names = [g['name'].decode('utf-8') if isinstance(g['name'], bytes) else g['name'] for g in groups]
            if expected_group in group_names:
                print(f"  ✅ {stream.split(':')[-2]}:{stream.split(':')[-1]:20s} → {expected_group}")
            else:
                print(f"  ⚠️  {stream.split(':')[-2]}:{stream.split(':')[-1]:20s} → Expected '{expected_group}', found {group_names}")
        except Exception as e:
            print(f"  ❌ {stream.split(':')[-2]}:{stream.split(':')[-1]:20s} → No groups (stream may not exist)")


async def main():
    """Run manual E2E tests"""
    print("\n" + "="*80)
    print("MANUAL E2E TEST - LeadsOrchestrator Delegation")
    print("="*80)
    print("\nPrerequisites:")
    print("  - LeadsOrchestrator consumer running (tenant=agentic-dev)")
    print("  - RAG Agent consumer running (tenant=agentic-dev)")
    print("  - Persistence Agent consumer running (tenant=agentic-dev)")
    print("  - Redis running on localhost:6379")
    print("\n" + "="*80)
    
    # Check initial state
    await check_redis_state()
    
    # Run tests
    test1_passed = await test_enrichment_delegation()
    test2_passed = await test_bulk_delegation()
    
    # Final state
    await check_redis_state()
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"  Enrichment → RAG:        {'✅ PASS' if test1_passed else '❌ FAIL'}")
    print(f"  Bulk → Persistence:      {'✅ PASS' if test2_passed else '❌ FAIL'}")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
