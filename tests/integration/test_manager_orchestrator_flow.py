#!/usr/bin/env python3
"""
Test Manager -> Orchestrators Delegation Flow

Tests the complete flow:
1. Send task to manager:tasks
2. Manager consumer reads and delegates to orchestrators:leads:tasks or orchestrators:outbound:tasks
3. Orchestrator consumer processes and publishes to results
4. Manager collects results and publishes to manager:results

Usage:
    # Terminal 1 - Start all consumers
    python start_all_consumers.py

    # Terminal 2 - Run this test
    python test_manager_orchestrator_flow.py
"""

import json
import time
import os
import sys
from datetime import datetime
import redis
import pytest


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_CONSUMERS") != "1",
    reason="Requires live Manager/Orchestrator consumers running (set RUN_LIVE_CONSUMERS=1)",
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

def test_manager_leads_flow(client, tenant_id):
    """Test 1: Manager -> Leads Orchestrator delegation"""
    print_header("TEST 1: Manager -> Leads Orchestrator Delegation")
    
    # Create test task
    task_id = f"test-leads-{int(time.time())}"
    task_data = {
        "task_id": task_id,
        "goal": "Find 50 AI/ML startups in San Francisco",
        "criteria": {
            "location": "San Francisco",
            "industry": "AI/Machine Learning",
            "count": 50,
            "min_funding": "1M"
        },
        "priority": "high"
    }
    
    manager_task_stream = f"{tenant_id}:manager:tasks"
    leads_task_stream = f"{tenant_id}:orchestrators:leads:tasks"
    leads_result_stream = f"{tenant_id}:orchestrators:leads:results"
    manager_result_stream = f"{tenant_id}:manager:results"
    
    print(f"[TASK] Test Task ID: {task_id}")
    print(f"   Goal: {task_data['goal']}")
    print(f"   Priority: {task_data['priority']}\n")
    
    # Step 1: Check current streams state
    print("Step [1] : Check streams before sending task...")
    manager_before = get_stream_info(client, manager_task_stream)
    leads_before = get_stream_info(client, leads_task_stream)
    leads_result_before = get_stream_info(client, leads_result_stream)
    
    print(f"  {manager_task_stream}: {manager_before['length']} messages")
    print(f"  {leads_task_stream}: {leads_before['length']} messages")
    print(f"  {leads_result_stream}: {leads_result_before['length']} messages\n")
    
    # Step 2: Send task to manager:tasks
    print("Step [2] : Sending task to manager:tasks...")
    try:
        msg_id = client.xadd(
            manager_task_stream,
            {
                "payload": json.dumps(task_data),
                "task_id": task_id,
                "priority": "high"
            }
        )
        print(f"  [OK] Task sent with message ID: {msg_id}\n")
    except Exception as e:
        print(f"  [ERROR] Failed to send task: {e}\n")
        return False
    
    # Step 3: Wait for delegation and processing
    print("Step [3] : Waiting for Manager consumer to delegate...")
    print("   (Manager consumer should read from manager:tasks)")
    print("   (and delegate to orchestrators:leads:tasks)\n")
    
    print("   Checking streams every 2 seconds (for 20 seconds)...")
    for i in range(10):
        time.sleep(2)
        
        leads_current = get_stream_info(client, leads_task_stream)
        leads_result_current = get_stream_info(client, leads_result_stream)
        manager_result_current = get_stream_info(client, manager_result_stream)
        
        status = f"   [{i+1}/10] {leads_task_stream}: {leads_current['length']} | {leads_result_stream}: {leads_result_current['length']} | {manager_result_stream}: {manager_result_current['length']}"
        print(status)
        
        # Check if leads result was created
        if leads_result_current['length'] > leads_result_before['length']:
            print(f"\n  [OK] Leads orchestrator completed! Result in {leads_result_stream}\n")
            break
    
    # Step 4: Check final state
    print("Step [4] : Checking final state...")
    manager_after = get_stream_info(client, manager_task_stream)
    leads_after = get_stream_info(client, leads_task_stream)
    leads_result_after = get_stream_info(client, leads_result_stream)
    manager_result_after = get_stream_info(client, manager_result_stream)
    
    print(f"  {manager_task_stream}: {manager_before['length']} -> {manager_after['length']}")
    print(f"  {leads_task_stream}: {leads_before['length']} -> {leads_after['length']}")
    print(f"  {leads_result_stream}: {leads_result_before['length']} -> {leads_result_after['length']}")
    print(f"  {manager_result_stream}: 0 -> {manager_result_after['length']}\n")
    
    # Step 5: Read and display results
    if leads_result_after['length'] > leads_result_before['length']:
        print("Step [5] : Reading results from orchestrators:leads:results...")
        try:
            messages = client.xrange(leads_result_stream, count=1)
            if messages:
                msg_id, data = messages[-1]
                result_payload = json.loads(data.get('payload', '{}'))
                print(f"  Message ID: {msg_id}")
                print(f"  Status: {result_payload.get('status', 'unknown')}")
                if 'error' in result_payload:
                    print(f"  Error: {result_payload['error']}")
                print(f"  Data keys: {list(result_payload.keys())}\n")
                return True
        except Exception as e:
            print(f"  [WARNING] Could not read result: {e}\n")
            return False
    else:
        print("  [WARNING] No results yet - consumer may still be processing or not running\n")
        print("  [NOTE] Make sure consumers are running:")
        print("     python start_all_consumers.py\n")
        return False

def test_manager_outreach_flow(client, tenant_id):
    """Test 2: Manager -> Outreach Orchestrator delegation"""
    print_header("TEST 2: Manager -> Outreach Orchestrator Delegation")
    
    # Create test task
    task_id = f"test-outreach-{int(time.time())}"
    task_data = {
        "task_id": task_id,
        "goal": "Launch Q4 email outreach campaign for enterprise customers",
        "campaign_data": {
            "target_segment": "Enterprise IT Decision Makers",
            "campaign_name": "Q4 Enterprise Engagement",
            "budget": "50000",
            "channels": ["email", "linkedin"],
            "num_prospects": 25
        },
        "priority": "high"
    }
    
    manager_task_stream = f"{tenant_id}:manager:tasks"
    outreach_task_stream = f"{tenant_id}:orchestrators:outbound:tasks"
    outreach_result_stream = f"{tenant_id}:orchestrators:outbound:results"
    manager_result_stream = f"{tenant_id}:manager:results"
    
    print(f"[TASK] Test Task ID: {task_id}")
    print(f"   Goal: {task_data['goal']}")
    print(f"   Campaign: {task_data['campaign_data']['campaign_name']}\n")
    
    # Step 1: Check current streams state
    print("Step [1] : Check streams before sending task...")
    manager_before = get_stream_info(client, manager_task_stream)
    outreach_before = get_stream_info(client, outreach_task_stream)
    outreach_result_before = get_stream_info(client, outreach_result_stream)
    
    print(f"  {manager_task_stream}: {manager_before['length']} messages")
    print(f"  {outreach_task_stream}: {outreach_before['length']} messages")
    print(f"  {outreach_result_stream}: {outreach_result_before['length']} messages\n")
    
    # Step 2: Send task to manager:tasks
    print("Step [2] : Sending task to manager:tasks...")
    try:
        msg_id = client.xadd(
            manager_task_stream,
            {
                "payload": json.dumps(task_data),
                "task_id": task_id,
                "priority": "high"
            }
        )
        print(f"  [OK] Task sent with message ID: {msg_id}\n")
    except Exception as e:
        print(f"  [ERROR] Failed to send task: {e}\n")
        return False
    
    # Step 3: Wait for delegation and processing
    print("Step [3] : Waiting for Manager consumer to delegate...")
    print("   (Manager consumer should read from manager:tasks)")
    print("   (and delegate to orchestrators:outbound:tasks)\n")
    
    print("   Checking streams every 2 seconds (for 20 seconds)...")
    for i in range(10):
        time.sleep(2)
        
        outreach_current = get_stream_info(client, outreach_task_stream)
        outreach_result_current = get_stream_info(client, outreach_result_stream)
        manager_result_current = get_stream_info(client, manager_result_stream)
        
        status = f"   [{i+1}/10] {outreach_task_stream}: {outreach_current['length']} | {outreach_result_stream}: {outreach_result_current['length']} | {manager_result_stream}: {manager_result_current['length']}"
        print(status)
        
        # Check if outreach result was created
        if outreach_result_current['length'] > outreach_result_before['length']:
            print(f"\n  [OK] Outreach orchestrator completed! Result in {outreach_result_stream}\n")
            break
    
    # Step 4: Check final state
    print("Step [4] : Checking final state...")
    manager_after = get_stream_info(client, manager_task_stream)
    outreach_after = get_stream_info(client, outreach_task_stream)
    outreach_result_after = get_stream_info(client, outreach_result_stream)
    manager_result_after = get_stream_info(client, manager_result_stream)
    
    print(f"  {manager_task_stream}: {manager_before['length']} -> {manager_after['length']}")
    print(f"  {outreach_task_stream}: {outreach_before['length']} -> {outreach_after['length']}")
    print(f"  {outreach_result_stream}: {outreach_result_before['length']} -> {outreach_result_after['length']}")
    print(f"  {manager_result_stream}: 0 -> {manager_result_after['length']}\n")
    
    # Step 5: Read and display results
    if outreach_result_after['length'] > outreach_result_before['length']:
        print("Step [5] : Reading results from orchestrators:outbound:results...")
        try:
            messages = client.xrange(outreach_result_stream, count=1)
            if messages:
                msg_id, data = messages[-1]
                result_payload = json.loads(data.get('payload', '{}'))
                print(f"  Message ID: {msg_id}")
                print(f"  Status: {result_payload.get('status', 'unknown')}")
                if 'error' in result_payload:
                    print(f"  Error: {result_payload['error']}")
                print(f"  Data keys: {list(result_payload.keys())}\n")
                return True
        except Exception as e:
            print(f"  [WARNING] Could not read result: {e}\n")
            return False
    else:
        print("  [WARNING] No results yet - consumer may still be processing or not running\n")
        print("  [NOTE] Make sure consumers are running:")
        print("     python start_all_consumers.py\n")
        return False

def verify_consumer_groups(client, tenant_id):
    """Verify consumer groups are created"""
    print_header("VERIFICATION: Consumer Groups")
    
    consumer_groups = [
        (f"{tenant_id}:manager:tasks", "manager-workers"),
        (f"{tenant_id}:orchestrators:leads:tasks", "leads-workers"),
        (f"{tenant_id}:orchestrators:outbound:tasks", "outbound-workers"),
    ]
    
    for stream, group in consumer_groups:
        try:
            groups = client.xinfo_groups(stream)
            group_names = [g['name'] for g in groups]
            if group in group_names:
                print(f"  [OK] {stream} -> {group} consumer group exists")
            else:
                print(f"  [WARNING] {stream} -> {group} consumer group NOT found (will be created by consumer)")
                print(f"      Available groups: {group_names}")
        except redis.ResponseError:
            print(f"  [WARNING] {stream} stream not found (will be created by first message)")

def main():
    """Main test execution"""
    print_header("THREE-TIER REDIS STREAMS TEST")
    print("Testing Manager -> Orchestrators Delegation Flow")
    print(f"Timestamp: {datetime.now().isoformat()}\n")
    
    # Get Redis client
    client = get_redis_client()
    tenant_id = os.getenv("TENANT_ID", "agentic-dev")
    
    print(f"Tenant ID: {tenant_id}")
    print(f"Using streams: {tenant_id}:manager:* and {tenant_id}:orchestrators:*\n")
    
    # Verify consumer groups
    verify_consumer_groups(client, tenant_id)
    
    # Run tests
    print_header("STARTING TESTS")
    print("[NOTE] Requirements:")
    print("   1. Consumers must be running in another terminal:")
    print("      python start_all_consumers.py")
    print("   2. OpenAI API key must be set in environment")
    print("   3. Redis Cloud connection must be working\n")
    
    input("Press Enter to start tests (or Ctrl+C to exit)...\n")
    
    # Test 1: Manager -> Leads
    result1 = test_manager_leads_flow(client, tenant_id)
    
    # Test 2: Manager -> Outreach
    result2 = test_manager_outreach_flow(client, tenant_id)
    
    # Summary
    print_header("TEST SUMMARY")
    print(f"Test 1 (Manager -> Leads):     {'[OK] PASSED' if result1 else '[WARNING] INCOMPLETE'}")
    print(f"Test 2 (Manager -> Outreach):  {'[OK] PASSED' if result2 else '[WARNING] INCOMPLETE'}")
    
    if result1 or result2:
        print("\n[OK] Three-tier flow is working!")
        print("\n[NOTE] Next steps:")
        print("   - Task 7: Test Manager -> Outreach Flow")
        print("   - Task 9-14: Build operational agent consumers")
        print("   - Task 15: Test complete end-to-end flow")
    else:
        print("\n[WARNING] Tests incomplete - check if consumers are running")
        print("\nTroubleshooting:")
        print("   1. Terminal 1: python start_all_consumers.py")
        print("   2. Check for errors in consumer output")
        print("   3. Verify OpenAI API key: echo $env:OPENAI_API_KEY")
        print("   4. Verify Redis connection: python verify_redis_streams.py")
    
    print("\n")

if __name__ == "__main__":
    main()
