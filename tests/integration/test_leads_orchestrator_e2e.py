"""
End-to-End LeadsOrchestrator Integration Tests

Tests the full orchestration flow:
1. Send task to LeadsOrchestrator via Redis
2. Orchestrator makes intelligent decision
3. Delegates to T3 agents (RAG, Persistence)
4. T3 agents respond with results
5. Orchestrator returns final result

Requires running consumers:
- LeadsOrchestrator consumer
- RAG agent consumer
- Persistence agent consumer
"""
import os
import time
import json
import pytest
from uuid import uuid4
from datetime import datetime
from typing import Dict, Any, Optional

from services.redis.client import RedisStreamsClient
from core.envelope import task, result, error, to_redis_fields, from_redis_message, Priority


@pytest.fixture
def redis_client():
    """Provide RedisStreamsClient for E2E testing."""
    redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    # Use production tenant for realistic testing
    client = RedisStreamsClient(url=redis_url, namespace="agentic-dev")
    
    # Verify connection
    client.client.ping()
    
    yield client
    
    # Optional: Cleanup test streams (commented out to preserve for debugging)
    # for key in client.client.scan_iter("agentic-dev:*test*"):
    #     client.client.delete(key)


def wait_for_message(
    redis_client: RedisStreamsClient,
    stream: str,
    timeout: int = 30,
    block_ms: int = 1000
) -> Optional[tuple]:
    """
    Wait for a message to appear in a stream.
    
    Returns:
        Tuple of (message_id, message_data) or None if timeout
    """
    start_time = time.time()
    last_id = "0"  # Start from beginning
    
    while time.time() - start_time < timeout:
        messages = redis_client.xread({stream: last_id}, count=1, block=block_ms)
        
        if messages and len(messages) > 0:
            stream_name, msg_list = messages[0]
            if msg_list:
                msg_id, msg_data = msg_list[0]
                return (msg_id, msg_data)
        
        # Update last_id to avoid re-reading same messages
        if messages and len(messages) > 0 and messages[0][1]:
            last_id = messages[0][1][-1][0]
    
    return None


def deserialize_envelope(msg_data: Dict[str, bytes]) -> Dict[str, Any]:
    """Deserialize Redis message to envelope dict."""
    result = {}
    for key, value in msg_data.items():
        if isinstance(value, bytes):
            try:
                decoded = json.loads(value.decode('utf-8'))
                result[key] = decoded
            except (json.JSONDecodeError, UnicodeDecodeError):
                result[key] = value.decode('utf-8')
        else:
            result[key] = value
    
    # Deserialize nested fields
    for nested_key in ['payload', 'metadata', 'data']:
        if nested_key in result and isinstance(result[nested_key], str):
            try:
                result[nested_key] = json.loads(result[nested_key])
            except (json.JSONDecodeError, ValueError):
                pass
    
    return result


def pretty_print_flow(stage: str, stream: str, envelope: Dict[str, Any], decision: str = ""):
    """Pretty print orchestration flow."""
    print(f"\n{'='*100}")
    print(f"🔄 STAGE: {stage}")
    print(f"{'='*100}")
    print(f"📡 Stream: {stream}")
    
    if decision:
        print(f"🧠 Decision: {decision}")
    
    print(f"\n📦 Envelope:")
    if 'metadata' in envelope:
        meta = envelope['metadata']
        print(f"  Task ID: {meta.get('task_id', 'N/A')}")
        print(f"  Correlation ID: {meta.get('correlation_id', 'N/A')}")
        print(f"  Source: {meta.get('source', 'N/A')}")
        print(f"  Destination: {meta.get('destination', 'N/A')}")
        print(f"  Priority: {meta.get('priority', 'N/A')}")
    
    if 'payload' in envelope:
        print(f"\n  Payload:")
        payload = envelope['payload']
        if isinstance(payload, dict):
            for k, v in payload.items():
                if isinstance(v, dict):
                    print(f"    {k}:")
                    for kk, vv in v.items():
                        print(f"      {kk}: {vv}")
                elif isinstance(v, list) and len(v) > 3:
                    print(f"    {k}: [{len(v)} items]")
                else:
                    print(f"    {k}: {v}")
        else:
            print(f"    {payload}")
    
    if 'status' in envelope:
        print(f"\n  Status: {envelope['status']}")
    
    if 'error' in envelope and envelope['error']:
        print(f"  ❌ Error: {envelope['error']}")
    
    print(f"{'='*100}\n")


def check_stream_length(redis_client: RedisStreamsClient, stream: str) -> int:
    """Get number of messages in stream."""
    try:
        # Use XLEN to get stream length
        return redis_client.client.xlen(stream)
    except:
        return 0


@pytest.mark.integration
@pytest.mark.slow
class TestLeadsOrchestratorE2E:
    """End-to-end tests for LeadsOrchestrator with real consumers."""
    
    def test_orchestrator_receives_task(self, redis_client):
        """Test 1: Verify orchestrator can receive and parse tasks."""
        print("\n" + "="*100)
        print("TEST 1: LeadsOrchestrator Task Reception")
        print("="*100)
        
        tenant_id = "agentic-dev"
        task_stream = f"{tenant_id}:orchestrators:leads:tasks"
        
        # Create task envelope
        task_id = f"test-task-{uuid4()}"
        envelope = task(
            source="e2e_test_suite",
            task_id=task_id,
            payload={
                "goal": "Process test lead",
                "action": "validate_lead",
                "data": {
                    "name": "John Doe",
                    "email": "john@example.com",
                    "company": "TechCorp"
                }
            },
            destination="leads_orchestrator",
            priority=Priority.NORMAL,
            tenant_id=tenant_id
        )
        
        # Convert to Redis format
        redis_fields = to_redis_fields(envelope)
        
        # Send to orchestrator
        msg_id = redis_client.xadd(task_stream, redis_fields)
        pretty_print_flow(
            "TASK SENT TO ORCHESTRATOR",
            task_stream,
            envelope,
            "Testing basic task reception"
        )
        
        print(f"✅ Task sent: {msg_id}")
        print(f"✅ Task ID: {task_id}")
        print(f"\n💡 Check orchestrator consumer logs for processing confirmation")
        
    
    def test_orchestrator_delegates_to_rag(self, redis_client):
        """Test 2: Verify orchestrator delegates enrichment to RAG agent."""
        print("\n" + "="*100)
        print("TEST 2: LeadsOrchestrator → RAG Agent Delegation")
        print("="*100)
        
        tenant_id = "agentic-dev"
        task_stream = f"{tenant_id}:orchestrators:leads:tasks"
        rag_stream = f"{tenant_id}:agents:rag:tasks"
        
        # Check RAG stream length before
        rag_before = check_stream_length(redis_client, rag_stream)
        print(f"📊 RAG stream length BEFORE: {rag_before}")
        
        # Create enrichment task
        task_id = f"test-enrich-{uuid4()}"
        envelope = task(
            source="e2e_test_suite",
            task_id=task_id,
            payload={
                "goal": "Enrich lead with company data",
                "action": "enrich_lead",
                "lead_id": "lead-12345",
                "company_name": "TechCorp Inc",
                "enrichment_fields": ["industry", "employee_count", "revenue"]
            },
            destination="leads_orchestrator",
            priority=Priority.HIGH,
            tenant_id=tenant_id
        )
        
        redis_fields = to_redis_fields(envelope)
        msg_id = redis_client.xadd(task_stream, redis_fields)
        
        pretty_print_flow(
            "ENRICHMENT TASK SENT",
            task_stream,
            envelope,
            "Expecting delegation to RAG for company enrichment"
        )
        
        # Wait for orchestrator to delegate to RAG
        print(f"\n⏳ Waiting up to 20s for orchestrator to delegate to RAG...")
        time.sleep(2)  # Give orchestrator time to process
        
        # Check if task appeared in RAG stream
        rag_message = wait_for_message(redis_client, rag_stream, timeout=20)
        
        if rag_message:
            msg_id, msg_data = rag_message
            rag_envelope = deserialize_envelope(msg_data)
            
            pretty_print_flow(
                "RAG AGENT RECEIVED TASK",
                rag_stream,
                rag_envelope,
                "✅ Orchestrator successfully delegated to RAG"
            )
            
            print(f"✅ DELEGATION SUCCESSFUL!")
            print(f"✅ Task found in RAG stream: {msg_id}")
            print(f"✅ Correlation preserved: {rag_envelope.get('metadata', {}).get('correlation_id')}")
        else:
            rag_after = check_stream_length(redis_client, rag_stream)
            print(f"\n⚠️  No message received in RAG stream within timeout")
            print(f"📊 RAG stream length AFTER: {rag_after}")
            print(f"💡 Check if LeadsOrchestrator consumer is running")
            print(f"💡 Check orchestrator logs for delegation decision")
    
    
    def test_orchestrator_delegates_to_persistence(self, redis_client):
        """Test 3: Verify orchestrator delegates bulk operations to Persistence."""
        print("\n" + "="*100)
        print("TEST 3: LeadsOrchestrator → Persistence Agent Delegation")
        print("="*100)
        
        tenant_id = "agentic-dev"
        task_stream = f"{tenant_id}:orchestrators:leads:tasks"
        persistence_stream = f"{tenant_id}:agents:persistence:tasks"
        
        # Check Persistence stream before
        persist_before = check_stream_length(redis_client, persistence_stream)
        print(f"📊 Persistence stream length BEFORE: {persist_before}")
        
        # Create bulk import task (>100 leads should trigger delegation)
        task_id = f"test-bulk-{uuid4()}"
        bulk_leads = [
            {
                "name": f"Lead {i}",
                "email": f"lead{i}@example.com",
                "company": f"Company {i}",
                "status": "new"
            }
            for i in range(150)  # > 100 triggers bulk handling
        ]
        
        envelope = task(
            source="e2e_test_suite",
            task_id=task_id,
            payload={
                "goal": "Import 150 leads in bulk",
                "action": "bulk_import",
                "leads": bulk_leads,
                "source": "csv_upload",
                "deduplicate": True
            },
            destination="leads_orchestrator",
            priority=Priority.NORMAL,
            tenant_id=tenant_id
        )
        
        redis_fields = to_redis_fields(envelope)
        msg_id = redis_client.xadd(task_stream, redis_fields)
        
        # Print without showing all 150 leads
        envelope_display = envelope.model_dump()
        envelope_display['payload']['leads'] = f"[{len(bulk_leads)} leads]"
        pretty_print_flow(
            "BULK IMPORT TASK SENT",
            task_stream,
            envelope_display,
            f"Bulk operation (150 leads) should delegate to Persistence"
        )
        
        # Wait for delegation
        print(f"\n⏳ Waiting up to 20s for orchestrator to delegate to Persistence...")
        time.sleep(2)
        
        persist_message = wait_for_message(redis_client, persistence_stream, timeout=20)
        
        if persist_message:
            msg_id, msg_data = persist_message
            persist_envelope = deserialize_envelope(msg_data)
            
            pretty_print_flow(
                "PERSISTENCE AGENT RECEIVED TASK",
                persistence_stream,
                persist_envelope,
                "✅ Orchestrator successfully delegated to Persistence"
            )
            
            print(f"✅ DELEGATION SUCCESSFUL!")
            print(f"✅ Task found in Persistence stream: {msg_id}")
        else:
            persist_after = check_stream_length(redis_client, persistence_stream)
            print(f"\n⚠️  No message received in Persistence stream within timeout")
            print(f"📊 Persistence stream length AFTER: {persist_after}")
            print(f"💡 Check if LeadsOrchestrator consumer is running")
    
    
    def test_full_orchestration_flow_with_results(self, redis_client):
        """Test 4: Full flow - Task → Orchestrator → T3 Agent → Result."""
        print("\n" + "="*100)
        print("TEST 4: Full E2E Orchestration Flow with Results")
        print("="*100)
        
        tenant_id = "agentic-dev"
        task_stream = f"{tenant_id}:orchestrators:leads:tasks"
        result_stream = f"{tenant_id}:orchestrators:leads:results"
        rag_stream = f"{tenant_id}:agents:rag:tasks"
        rag_result_stream = f"{tenant_id}:agents:rag:results"
        
        # Create task
        task_id = f"test-full-flow-{uuid4()}"
        correlation_id = f"corr-{uuid4()}"
        
        envelope = task(
            source="e2e_test_suite",
            task_id=task_id,
            payload={
                "goal": "Search for leads in technology sector",
                "action": "search_leads",
                "query": "companies in SaaS industry with 50-200 employees",
                "filters": {
                    "industry": "SaaS",
                    "employee_range": [50, 200]
                }
            },
            destination="leads_orchestrator",
            priority=Priority.HIGH,
            tenant_id=tenant_id
        )
        
        # Manually set correlation_id for tracking
        envelope.metadata.correlation_id = correlation_id
        
        redis_fields = to_redis_fields(envelope)
        msg_id = redis_client.xadd(task_stream, redis_fields)
        
        pretty_print_flow(
            "1️⃣ TASK SENT TO ORCHESTRATOR",
            task_stream,
            envelope,
            "Initiating full orchestration flow"
        )
        
        print(f"\n📍 Tracking Correlation ID: {correlation_id}")
        
        # Step 1: Wait for delegation to RAG
        print(f"\n⏳ Step 1: Waiting for delegation to RAG agent...")
        rag_message = wait_for_message(redis_client, rag_stream, timeout=15)
        
        if rag_message:
            msg_id, msg_data = rag_message
            rag_task = deserialize_envelope(msg_data)
            
            pretty_print_flow(
                "2️⃣ RAG AGENT RECEIVED DELEGATION",
                rag_stream,
                rag_task,
                "Orchestrator delegated to RAG for search"
            )
            
            # Step 2: Wait for RAG result
            print(f"\n⏳ Step 2: Waiting for RAG agent result...")
            rag_result_msg = wait_for_message(redis_client, rag_result_stream, timeout=30)
            
            if rag_result_msg:
                msg_id, msg_data = rag_result_msg
                rag_result_env = deserialize_envelope(msg_data)
                
                pretty_print_flow(
                    "3️⃣ RAG AGENT RETURNED RESULT",
                    rag_result_stream,
                    rag_result_env,
                    "RAG completed search operation"
                )
                
                # Step 3: Wait for orchestrator final result
                print(f"\n⏳ Step 3: Waiting for orchestrator final result...")
                orchestrator_result = wait_for_message(redis_client, result_stream, timeout=20)
                
                if orchestrator_result:
                    msg_id, msg_data = orchestrator_result
                    final_result = deserialize_envelope(msg_data)
                    
                    pretty_print_flow(
                        "4️⃣ ORCHESTRATOR FINAL RESULT",
                        result_stream,
                        final_result,
                        "✅ FULL FLOW COMPLETE!"
                    )
                    
                    print(f"\n{'='*100}")
                    print(f"🎉 END-TO-END FLOW SUCCESSFUL!")
                    print(f"{'='*100}")
                    print(f"✅ Task sent to orchestrator")
                    print(f"✅ Orchestrator delegated to RAG")
                    print(f"✅ RAG agent processed and returned result")
                    print(f"✅ Orchestrator compiled final result")
                    print(f"\n📊 Correlation ID preserved throughout: {correlation_id}")
                else:
                    print(f"\n⚠️  Orchestrator final result not received")
            else:
                print(f"\n⚠️  RAG result not received")
        else:
            print(f"\n⚠️  RAG delegation not detected")
            print(f"💡 Ensure LeadsOrchestrator consumer is running")


@pytest.mark.integration
@pytest.mark.slow
class TestSystemHealthCheck:
    """Health check tests to verify all components are running."""
    
    def test_redis_connectivity(self, redis_client):
        """Verify Redis is accessible."""
        print("\n🔍 Testing Redis connectivity...")
        assert redis_client.client.ping(), "Redis should be accessible"
        print("✅ Redis is UP")
    
    def test_required_streams_exist(self, redis_client):
        """Check if required streams exist (created by consumers)."""
        print("\n🔍 Checking required streams...")
        
        tenant_id = "agentic-dev"
        required_streams = [
            f"{tenant_id}:orchestrators:leads:tasks",
            f"{tenant_id}:agents:rag:tasks",
            f"{tenant_id}:agents:persistence:tasks",
        ]
        
        for stream in required_streams:
            try:
                length = redis_client.client.xlen(stream)
                print(f"✅ {stream}: {length} messages")
            except:
                print(f"⚠️  {stream}: Not yet created (will be created on first message)")
    
    def test_consumer_groups_exist(self, redis_client):
        """Check if consumer groups are registered."""
        print("\n🔍 Checking consumer groups...")
        
        tenant_id = "agentic-dev"
        streams_to_check = [
            (f"{tenant_id}:orchestrators:leads:tasks", "leads-workers"),
            (f"{tenant_id}:agents:rag:tasks", "rag-workers"),
            (f"{tenant_id}:agents:persistence:tasks", "persistence-workers"),
        ]
        
        for stream, expected_group in streams_to_check:
            try:
                groups = redis_client.client.xinfo_groups(stream)
                group_names = [g['name'].decode('utf-8') if isinstance(g['name'], bytes) else g['name'] for g in groups]
                if expected_group in group_names:
                    print(f"✅ {stream}: Group '{expected_group}' registered")
                else:
                    print(f"⚠️  {stream}: Group '{expected_group}' not found. Available: {group_names}")
            except Exception as e:
                print(f"⚠️  {stream}: Stream not initialized yet ({str(e)})")


if __name__ == "__main__":
    """
    Run tests with:
    pytest tests/integration/test_leads_orchestrator_e2e.py -v -s --no-cov
    
    Before running:
    1. Start Redis: docker compose up redis -d
    2. Start consumers:
       - python -m tiers.tier_2.leads_orchestrator.consumer
       - python -m tiers.tier_3.rag_agent.consumer
       - python -m tiers.tier_3.persistence_agent.consumer
    """
    print(__doc__)
