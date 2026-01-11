#!/usr/bin/env python
"""
End-to-End Test: Manager -> Leads -> RAG flow
Tests both delegation tiers in a single script
"""
import os
import pytest
import sys
import json
import time
import redis
import subprocess
import signal
from datetime import datetime, timezone
from dotenv import load_dotenv

import argparse

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Load environment variables from .env file
load_dotenv()


# NOTE:
# This module spins up real consumers and uses Redis Streams.
# It is intentionally opt-in so that local/CI unit-style `pytest` runs don't hang.
if os.getenv("RUN_E2E_TESTS", "0").lower() not in {"1", "true", "yes"}:
    pytest.skip(
        "E2E flow test is opt-in. Set RUN_E2E_TESTS=1 to enable.",
        allow_module_level=True,
    )

from core.envelope import task as create_task_envelope, to_redis_fields

os.environ.setdefault('REDIS_URL', os.getenv('REDIS_URL', 'redis://localhost:6379/0'))
os.environ.setdefault('TENANT_ID', os.getenv('TENANT_ID', 'agentic-dev'))

redis_url = os.getenv('REDIS_URL')
tenant_id = os.getenv('TENANT_ID')

def print_section(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")

def start_consumers():
    """Start all consumers in background"""
    print_section("Starting All Consumers")
    
    # Start consumers
    # Inherit stdout/stderr to see logs in real-time
    start_script = os.path.join(project_root, 'start_all_consumers.py')
    
    env = {
        **os.environ, 
        'REDIS_URL': redis_url, 
        'TENANT_ID': tenant_id,
    }
    
    process = subprocess.Popen(
        [sys.executable, start_script],
        env=env,
        cwd=project_root  # Ensure CWD is project root
    )
    
    # Give them time to start
    time.sleep(3)
    print("[OK] Consumers started")
    return process

def stop_consumers(process):
    """Stop consumers gracefully"""
    if not process:
        return
        
    print_section("Stopping Consumers")
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
    print("[OK] Consumers stopped")

def test_manager_leads_flow():
    """Test Manager -> Leads delegation"""
    print_section("TEST 1: Manager -> Leads Delegation")
    
    client = redis.Redis.from_url(redis_url, decode_responses=True)
    
    # Get baseline
    leads_before = client.xlen(f'{tenant_id}:orchestrators:leads:tasks')
    manager_before = client.xlen(f'{tenant_id}:manager:tasks')
    
    print(f"Baseline:")
    print(f"  leads:tasks: {leads_before}")
    print(f"  manager:tasks: {manager_before}\n")
    
    # Send test task
    task_id = f"test-leads-{int(time.time())}"
    task_data = {
        "task_id": task_id,
        "goal": "Find 50 AI startups in San Francisco",
        "criteria": {"location": "San Francisco", "industry": "AI"},
    }
    
    print(f"Sending test task: {task_id}")
    print(f"  Goal: {task_data['goal']}\n")
    
    # Create envelope
    envelope = create_task_envelope(
        source="e2e_test",
        task_id=task_id,
        payload=task_data,
        destination="manager_agent",
        tenant_id=tenant_id
    )
    
    msg_id = client.xadd(
        f'{tenant_id}:manager:tasks',
        to_redis_fields(envelope)
    )
    print(f"Task added to manager:tasks: {msg_id}\n")
    
    # Wait for processing
    print("Waiting 15 seconds for delegation...\n")
    time.sleep(15)
    
    # Check results
    leads_after = client.xlen(f'{tenant_id}:orchestrators:leads:tasks')
    manager_after = client.xlen(f'{tenant_id}:manager:tasks')
    
    print(f"After processing:")
    print(f"  leads:tasks: {leads_before} -> {leads_after}")
    print(f"  manager:tasks: {manager_before} -> {manager_after}\n")
    
    if leads_after > leads_before:
        print("[OK] MANAGER->LEADS DELEGATION SUCCESSFUL!")
        print(f"     Delegated {leads_after - leads_before} task(s) to Leads Orchestrator")
        return True
    else:
        print("[WARNING] No delegation detected")
        return False

def test_leads_rag_flow():
    """Test Leads -> RAG delegation"""
    print_section("TEST 2: Leads -> RAG Delegation")
    
    client = redis.Redis.from_url(redis_url, decode_responses=True)
    
    # Get baseline
    rag_before = client.xlen(f'{tenant_id}:agents:rag:tasks')
    leads_before = client.xlen(f'{tenant_id}:orchestrators:leads:tasks')
    
    print(f"Baseline:")
    print(f"  rag:tasks: {rag_before}")
    print(f"  leads:tasks: {leads_before}\n")
    
    # Send test task to leads (bypassing manager)
    task_id = f"test-rag-{int(time.time())}"
    task_data = {
        "task_id": task_id,
        "goal": "Enrich lead data for Acme Corp",
        "data": {"lead_id": "lead_123", "company": "Acme Corp"},
    }
    
    print(f"Sending test task to leads:tasks: {task_id}")
    print(f"  Goal: {task_data['goal']}\n")
    
    # Create envelope
    envelope = create_task_envelope(
        source="e2e_test",
        task_id=task_id,
        payload=task_data,
        destination="leads_orchestrator",
        tenant_id=tenant_id
    )
    
    msg_id = client.xadd(
        f'{tenant_id}:orchestrators:leads:tasks',
        to_redis_fields(envelope)
    )
    print(f"Task added to leads:tasks: {msg_id}\n")
    
    # Wait for processing
    print("Waiting 15 seconds for RAG delegation...\n")
    time.sleep(15)
    
    # Check results
    rag_after = client.xlen(f'{tenant_id}:agents:rag:tasks')
    leads_after = client.xlen(f'{tenant_id}:orchestrators:leads:tasks')
    
    print(f"After processing:")
    print(f"  rag:tasks: {rag_before} -> {rag_after}")
    print(f"  leads:tasks: {leads_before} -> {leads_after}\n")
    
    if rag_after > rag_before:
        print("[OK] LEADS->RAG DELEGATION SUCCESSFUL!")
        print(f"     Delegated {rag_after - rag_before} task(s) to RAG Agent")
        return True
    else:
        print("[WARNING] No delegation detected")
        return False


def test_manager_outbound_tier3_flow():
    """Test Manager -> Outbound Orchestrator -> Tier-3 agent results."""
    print_section("TEST 3: Manager -> Outbound -> Tier-3")

    client = redis.Redis.from_url(redis_url, decode_responses=True)

    outbound_tasks_stream = f"{tenant_id}:orchestrators:outbound:tasks"
    outbound_results_stream = f"{tenant_id}:orchestrators:outbound:results"
    copywriter_results_stream = f"{tenant_id}:agents:copywriter:results"
    booking_results_stream = f"{tenant_id}:agents:booking:results"
    sequencing_results_stream = f"{tenant_id}:agents:sequencing:results"

    # Baseline
    baseline = {
        "outbound_tasks": client.xlen(outbound_tasks_stream),
        "outbound_results": client.xlen(outbound_results_stream),
        "copywriter_results": client.xlen(copywriter_results_stream),
        "booking_results": client.xlen(booking_results_stream),
        "sequencing_results": client.xlen(sequencing_results_stream),
    }

    print("Baseline:")
    for k, v in baseline.items():
        print(f"  {k}: {v}")
    print("")

    # Send a Manager task that will route to outbound, with deterministic delegations
    task_id = f"test-outbound-{int(time.time())}"
    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    task_data = {
        "task_id": task_id,
        "goal": "Launch an outreach campaign with copy, booking, and sequencing",
        "delegations": {
            "copywriter": {
                "campaign_id": "camp_e2e_001",
                "lead_id": "lead_e2e_001",
                "channel": "email",
                "tone": "professional",
                "goal": "book_meeting",
                "context": {
                    "recipient_name": "Sam",
                    "company_name": "ExampleCo",
                    "value_prop": "an AI outreach assistant",
                    "call_to_action": "Are you open to a 15-minute intro call next week?",
                },
            },
            "booking": {
                "campaign_id": "camp_e2e_001",
                "lead_id": "lead_e2e_001",
                "meeting_type": "discovery_call",
                "duration_minutes": 30,
                "preferred_times": [now_iso],
                "provider": "google",
                "attendees": [{"email": "sam@example.com", "name": "Sam"}],
                "context": "E2E booking request",
            },
            "sequencing": {
                "campaign_id": "camp_e2e_001",
                "lead_id": "lead_e2e_001",
                "optimization_goal": "maximize_reply_rate",
                "steps": [
                    {"channel": "email", "delay_minutes": 0, "metadata": {"variant": "A"}},
                    {"channel": "linkedin", "delay_minutes": 60 * 24 * 3, "metadata": {}},
                ],
            },
        },
    }

    print(f"Sending test task: {task_id}")
    print(f"  Goal: {task_data['goal']}\n")

    envelope = create_task_envelope(
        source="e2e_test",
        task_id=task_id,
        payload=task_data,
        destination="manager_agent",
        tenant_id=tenant_id,
    )

    msg_id = client.xadd(
        f"{tenant_id}:manager:tasks",
        to_redis_fields(envelope),
    )
    print(f"Task added to manager:tasks: {msg_id}\n")

    # Poll up to ~30s for outbound results + tier3 results
    print("Waiting up to 30 seconds for outbound + tier3 results...\n")
    max_iters = 15
    for i in range(max_iters):
        time.sleep(2)
        current = {
            "outbound_tasks": client.xlen(outbound_tasks_stream),
            "outbound_results": client.xlen(outbound_results_stream),
            "copywriter_results": client.xlen(copywriter_results_stream),
            "booking_results": client.xlen(booking_results_stream),
            "sequencing_results": client.xlen(sequencing_results_stream),
        }

        status = (
            f"  [{i+1}/{max_iters}] outbound:tasks {baseline['outbound_tasks']}->{current['outbound_tasks']} | "
            f"outbound:results {baseline['outbound_results']}->{current['outbound_results']} | "
            f"copywriter:results {baseline['copywriter_results']}->{current['copywriter_results']} | "
            f"booking:results {baseline['booking_results']}->{current['booking_results']} | "
            f"sequencing:results {baseline['sequencing_results']}->{current['sequencing_results']}"
        )
        print(status)

        got_outbound = current["outbound_results"] > baseline["outbound_results"]
        got_copy = current["copywriter_results"] > baseline["copywriter_results"]
        got_booking = current["booking_results"] > baseline["booking_results"]
        got_seq = current["sequencing_results"] > baseline["sequencing_results"]

        if got_outbound and got_copy and got_booking and got_seq:
            print("\n[OK] OUTBOUND + TIER-3 FLOW SUCCESSFUL!\n")
            return True

    print("\n[WARNING] Incomplete outbound/tier3 flow - check consumer logs")
    return False

def main():
    parser = argparse.ArgumentParser(description='Run End-to-End Flow Test')
    parser.add_argument('--spawn-consumers', action='store_true', 
                        help='Spawn new consumers for the test (default: False, uses existing)')
    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("  AGENTIC SYSTEM - END-TO-END FLOW TEST")
    print("=" * 70)
    print(f"\nTenant: {tenant_id}")
    print(f"Redis: {redis_url.split('@')[-1] if '@' in redis_url else redis_url}")
    
    # Start consumers if requested
    consumer_process = None
    if args.spawn_consumers:
        consumer_process = start_consumers()
    else:
        print("\n[INFO] Using existing consumers (Current Clients).")
        print("       Ensure 'python start_all_consumers.py' is running.")
    
    try:
        # Run tests
        test1_pass = test_manager_leads_flow()
        test2_pass = test_leads_rag_flow()
        test3_pass = test_manager_outbound_tier3_flow()
        
        # Summary
        print_section("TEST SUMMARY")
        print(f"Test 1 (Manager -> Leads): {'[OK] PASSED' if test1_pass else '[WARNING] INCOMPLETE'}")
        print(f"Test 2 (Leads -> RAG):     {'[OK] PASSED' if test2_pass else '[WARNING] INCOMPLETE'}")
        print(f"Test 3 (Outbound + Tier-3): {'[OK] PASSED' if test3_pass else '[WARNING] INCOMPLETE'}")
        
        if test1_pass and test2_pass and test3_pass:
            print("\n[OK] END-TO-END FLOW VERIFIED!")
            print("    Manager + outbound + Tier-3 delegation pipeline is working correctly.")
        elif test1_pass or test3_pass:
            print("\n[OK] PARTIAL END-TO-END VERIFIED")
            print("    Some flows succeeded; see warnings above.")
        else:
            print("\n[WARNING] Tests incomplete - check consumer logs")
        
    finally:
        # Stop consumers if we started them
        if consumer_process:
            stop_consumers(consumer_process)
    
    print("\n")

if __name__ == "__main__":
    main()
