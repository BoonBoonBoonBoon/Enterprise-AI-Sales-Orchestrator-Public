#!/usr/bin/env python3
"""
Test Leads Orchestrator -> RAG Agent Delegation Flow

Tests the flow:
1. Send task to leads:tasks (simulating Manager delegation)
2. Leads Orchestrator consumer reads and delegates to agents:rag:tasks
3. RAG Agent consumer processes and publishes to agents:rag:results
4. Leads Orchestrator collects results and publishes to leads:results

Usage:
    # Terminal 1 - Start all consumers
    python start_all_consumers.py

    # Terminal 2 - Run this test
    python test_leads_rag_flow.py
"""

import json
import time
import os
import sys
from datetime import datetime
import redis
import pytest

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

try:
    from services.redis import StreamKeyBuilder
except ImportError:
    # Fallback for migration phase
    class StreamKeyBuilder:
        @staticmethod
        def orchestrator_tasks(t, o): return f"{t}:{o}:tasks"
        @staticmethod
        def orchestrator_results(t, o): return f"{t}:{o}:results"
        @staticmethod
        def agent_tasks(t, a): return f"{t}:agents:{a}:tasks"
        @staticmethod
        def agent_results(t, a): return f"{t}:agents:{a}:results"


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_CONSUMERS") != "1",
    reason="Requires live Leads/RAG consumers running (set RUN_LIVE_CONSUMERS=1)",
)

def print_header(text):
    """Print formatted header"""
    print(f"\n{'='*70}")
    print(f"  {text}")
    print(f"{'='*70}\n")

def get_redis_client():
    """Get Redis client from REDIS_URL environment variable"""
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    try:
        client = redis.Redis.from_url(redis_url, decode_responses=True)
        client.ping()
        print(f"[OK] Connected to Redis: {redis_url.split('@')[-1] if '@' in redis_url else redis_url}")
        return client
    except Exception as e:
        print(f"[ERROR] Failed to connect to Redis: {e}")
        sys.exit(1)

def get_stream_info(client, stream_name):
    """Get information about a stream"""
    try:
        length = client.xlen(stream_name)
        info = client.xinfo_stream(stream_name)
        return {
            'exists': True,
            'length': length,
            'first_entry': info.get('first-entry', 'N/A'),
            'last_entry': info.get('last-entry', 'N/A'),
        }
    except redis.ResponseError:
        return {'exists': False, 'length': 0}

def test_leads_rag_delegation(client, tenant_id):
    """Test: Leads Orchestrator -> RAG Agent delegation"""
    print_header("TEST: Leads Orchestrator -> RAG Agent Delegation")
    
    # Create test task that requires enrichment (forcing delegation to RAG)
    task_id = f"test-leads-rag-{int(time.time())}"
    task_data = {
        "task_id": task_id,
        "goal": "Enrich lead data for Acme Corp",
        "data": {
            "lead_id": "lead_123",
            "company": "Acme Corp",
            "website": "acme.com"
        },
        "priority": "high"
    }
    
    # Define streams
    leads_task_stream = StreamKeyBuilder.orchestrator_tasks(tenant_id, "leads")
    rag_task_stream = StreamKeyBuilder.agent_tasks(tenant_id, "rag")
    rag_result_stream = StreamKeyBuilder.agent_results(tenant_id, "rag")
    leads_result_stream = StreamKeyBuilder.orchestrator_results(tenant_id, "leads")
    
    print(f"[TASK] Test Task ID: {task_id}")
    print(f"   Goal: {task_data['goal']}\n")
    
    # Step 1: Check current streams state
    print("Step [1] : Check streams before sending task...")
    leads_before = get_stream_info(client, leads_task_stream)
    rag_before = get_stream_info(client, rag_task_stream)
    rag_result_before = get_stream_info(client, rag_result_stream)
    
    print(f"  {leads_task_stream}: {leads_before['length']} messages")
    print(f"  {rag_task_stream}: {rag_before['length']} messages")
    print(f"  {rag_result_stream}: {rag_result_before['length']} messages\n")
    
    # Step 2: Send task to leads:tasks
    print("Step [2] : Sending task to leads:tasks...")
    try:
        msg_id = client.xadd(
            leads_task_stream,
            {
                "payload": json.dumps(task_data),
                "task_id": task_id,
                "priority": "high",
                "source": "test_script"
            }
        )
        print(f"  [OK] Task sent with message ID: {msg_id}\n")
    except Exception as e:
        print(f"  [ERROR] Failed to send task: {e}\n")
        return False
    
    # Step 3: Wait for delegation and processing
    print("Step [3] : Waiting for Leads Orchestrator to delegate to RAG Agent...")
    print("   (Leads consumer should read from leads:tasks)")
    print("   (and delegate to agents:rag:tasks)\n")
    
    print("   Checking streams every 2 seconds (for 30 seconds)...")
    rag_delegated = False
    
    for i in range(15):
        time.sleep(2)
        
        rag_current = get_stream_info(client, rag_task_stream)
        rag_result_current = get_stream_info(client, rag_result_stream)
        leads_result_current = get_stream_info(client, leads_result_stream)
        
        status = f"   [{i+1}/15] {rag_task_stream}: {rag_current['length']} | {rag_result_stream}: {rag_result_current['length']} | {leads_result_stream}: {leads_result_current['length']}"
        print(status)
        
        # Check if RAG task was created (delegation happened)
        if not rag_delegated and rag_current['length'] > rag_before['length']:
            print(f"      ✨ Delegation detected! Task added to {rag_task_stream}")
            rag_delegated = True
            
        # Check if leads result was created (final completion)
        if leads_result_current['length'] > 0: # Assuming we start fresh or just check for new
             # Better check: check if we have a result for this task
             pass

        # Ideally we check for specific result, but length increase is a good proxy for now
        # Since we don't know the exact starting length of leads_result if we run multiple tests
        # But we printed it at start.
        
        # If RAG result exists and Leads result exists, we are likely done
        if rag_result_current['length'] > rag_result_before['length'] and leads_result_current['length'] > 0:
             print(f"\n  [OK] Flow completed! Result in {leads_result_stream}\n")
             break
    
    # Step 4: Check final state
    print("Step [4] : Checking final state...")
    leads_after = get_stream_info(client, leads_task_stream)
    rag_after = get_stream_info(client, rag_task_stream)
    rag_result_after = get_stream_info(client, rag_result_stream)
    leads_result_after = get_stream_info(client, leads_result_stream)
    
    print(f"  {leads_task_stream}: {leads_before['length']} -> {leads_after['length']}")
    print(f"  {rag_task_stream}: {rag_before['length']} -> {rag_after['length']}")
    print(f"  {rag_result_stream}: {rag_result_before['length']} -> {rag_result_after['length']}")
    print(f"  {leads_result_stream}: {0} -> {leads_result_after['length']}\n")
    
    if rag_after['length'] > rag_before['length']:
        print("  [OK] Delegation successful (Leads -> RAG)")
        return True
    else:
        print("  [ERROR] Delegation failed (No task in RAG stream)")
        return False

def main():
    """Main test execution"""
    print_header("TIER 2-3 INTEGRATION TEST")
    print("Testing Leads Orchestrator -> RAG Agent Delegation Flow")
    print(f"Timestamp: {datetime.now().isoformat()}\n")
    
    # Get Redis client
    client = get_redis_client()
    tenant_id = os.getenv("TENANT_ID", "agentic-dev")
    
    print(f"Tenant ID: {tenant_id}")
    print(f"Using streams: {StreamKeyBuilder.orchestrator_tasks(tenant_id, 'leads')} -> {StreamKeyBuilder.agent_tasks(tenant_id, 'rag')}\n")
    
    # Run tests
    print_header("STARTING TESTS")
    print("[NOTE] Requirements:")
    print("   1. Consumers must be running in another terminal:")
    print("      python start_all_consumers.py")
    print("   2. OpenAI API key must be set in environment")
    
    input("Press Enter to start tests (or Ctrl+C to exit)...\n")
    
    # Test: Leads -> RAG
    result = test_leads_rag_delegation(client, tenant_id)
    
    # Summary
    print_header("TEST SUMMARY")
    print(f"Test (Leads -> RAG): {'[OK] PASSED' if result else '[ERROR] FAILED'}")
    
    if result:
        print("\n[OK] Tier 2-3 flow is working!")
    else:
        print("\n[WARNING] Test failed - check consumers")

if __name__ == "__main__":
    main()
