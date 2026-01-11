"""
Test Manager → Orchestrator Delegation via Redis Streams

This script tests the complete delegation flow:
1. Manager delegates to Leads Orchestrator
2. Manager delegates to Outreach Orchestrator
3. Verifies streams are created correctly
4. Shows how to check task status
"""

import os
import sys
import asyncio
import json
from datetime import datetime
from pathlib import Path

# Ensure project root on path
repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import redis
from tiers.tier_1.manager.tools.delegation_tools import DelegationTools


def test_stream_setup():
    """Test Redis stream setup for Manager delegation"""
    
    print("=" * 80)
    print("MANAGER → ORCHESTRATOR DELEGATION TEST")
    print("=" * 80)
    print()
    
    # Connect to Redis
    print("📡 Connecting to Redis...")
    redis_client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    tenant_id = os.getenv("TENANT_ID", "agentic-dev")
    
    # Initialize delegation tools
    delegation = DelegationTools(redis_client, tenant_id)
    print(f"✅ Connected (tenant: {tenant_id})")
    print()
    
    # Test 1: Delegate to Leads Orchestrator
    print("=" * 80)
    print("TEST 1: MANAGER → LEADS ORCHESTRATOR")
    print("=" * 80)
    
    leads_goal = "Find 50 AI startups in San Francisco with 10-50 employees"
    leads_criteria = {
        "industry": "artificial_intelligence",
        "location": "San Francisco, CA",
        "company_size": {"min": 10, "max": 50},
        "technologies": ["machine_learning", "nlp", "computer_vision"]
    }
    
    print(f"Goal: {leads_goal}")
    print(f"Criteria: {json.dumps(leads_criteria, indent=2)}")
    print()
    
    result = delegation.delegate_to_leads_orchestrator(
        goal=leads_goal,
        criteria=leads_criteria,
        priority="high"
    )
    
    print(f"✅ Task delegated successfully!")
    print(f"   Task ID: {result['task_id']}")
    print(f"   Stream: {result['stream']}")
    print(f"   Stream ID: {result['stream_id']}")
    print()
    
    # Verify stream exists
    leads_stream = f"{tenant_id}:orchestrators:leads:tasks"
    stream_info = redis_client.xinfo_stream(leads_stream)
    print(f"📊 Stream Info for {leads_stream}:")
    print(f"   Length: {stream_info['length']} messages")
    print(f"   First Entry: {stream_info.get('first-entry', 'N/A')}")
    print(f"   Last Entry: {stream_info.get('last-entry', 'N/A')}")
    print()
    
    # Test 2: Delegate to Outreach Orchestrator
    print("=" * 80)
    print("TEST 2: MANAGER → OUTREACH ORCHESTRATOR")
    print("=" * 80)
    
    outreach_goal = "Launch Q4 enterprise email campaign with multi-channel follow-up"
    campaign_data = {
        "campaign_name": "Q4 Enterprise Outreach",
        "leads": ["lead-123", "lead-456", "lead-789"],
        "channels": ["email", "linkedin", "phone"],
        "touchpoints": [
            {"channel": "email", "delay_days": 0, "template": "cold_intro"},
            {"channel": "linkedin", "delay_days": 3, "template": "connection_request"},
            {"channel": "phone", "delay_days": 7, "template": "discovery_call"},
            {"channel": "email", "delay_days": 10, "template": "follow_up"}
        ],
        "personalization": {
            "tone": "professional",
            "focus": "AI automation ROI"
        }
    }
    
    print(f"Goal: {outreach_goal}")
    print(f"Campaign: {campaign_data['campaign_name']}")
    print(f"Leads: {len(campaign_data['leads'])}")
    print(f"Channels: {', '.join(campaign_data['channels'])}")
    print(f"Touchpoints: {len(campaign_data['touchpoints'])}")
    print()
    
    result = delegation.delegate_to_outreach_orchestrator(
        goal=outreach_goal,
        campaign_data=campaign_data,
        priority="high"
    )
    
    print(f"✅ Task delegated successfully!")
    print(f"   Task ID: {result['task_id']}")
    print(f"   Stream: {result['stream']}")
    print(f"   Stream ID: {result['stream_id']}")
    print()
    
    # Verify stream exists
    outreach_stream = f"{tenant_id}:orchestrators:outbound:tasks"
    stream_info = redis_client.xinfo_stream(outreach_stream)
    print(f"📊 Stream Info for {outreach_stream}:")
    print(f"   Length: {stream_info['length']} messages")
    print(f"   First Entry: {stream_info.get('first-entry', 'N/A')}")
    print(f"   Last Entry: {stream_info.get('last-entry', 'N/A')}")
    print()
    
    # Test 3: Verify Consumer Groups
    print("=" * 80)
    print("TEST 3: CONSUMER GROUPS")
    print("=" * 80)
    
    print("Checking for consumer groups...")
    print()
    
    # Check Leads consumer group
    try:
        leads_groups = redis_client.xinfo_groups(leads_stream)
        print(f"✅ {leads_stream} consumer groups:")
        for group in leads_groups:
            print(f"   - {group['name'].decode() if isinstance(group['name'], bytes) else group['name']}")
            print(f"     Consumers: {group['consumers']}")
            print(f"     Pending: {group['pending']}")
    except Exception as e:
        print(f"⚠️  No consumer groups for {leads_stream}: {e}")
        print(f"   Run: python agent/orchestrators/leads_orchestrator/consumer.py")
    print()
    
    # Check Outreach consumer group
    try:
        outreach_groups = redis_client.xinfo_groups(outreach_stream)
        print(f"✅ {outreach_stream} consumer groups:")
        for group in outreach_groups:
            print(f"   - {group['name'].decode() if isinstance(group['name'], bytes) else group['name']}")
            print(f"     Consumers: {group['consumers']}")
            print(f"     Pending: {group['pending']}")
    except Exception as e:
        print(f"⚠️  No consumer groups for {outreach_stream}: {e}")
        print(f"   Run: python agent/orchestrators/outreach_orchestrator/consumer.py")
    print()
    
    # Test 4: List All Streams
    print("=" * 80)
    print("TEST 4: ALL ACTIVE STREAMS")
    print("=" * 80)
    
    print(f"Scanning for {tenant_id}:* streams...")
    print()
    
    # Get all keys matching pattern
    stream_pattern = f"{tenant_id}:*:tasks"
    all_streams = []
    
    for key in redis_client.scan_iter(match=stream_pattern):
        key_str = key.decode() if isinstance(key, bytes) else key
        try:
            info = redis_client.xinfo_stream(key_str)
            all_streams.append({
                "stream": key_str,
                "length": info["length"],
                "type": "tasks"
            })
        except:
            pass
    
    # Also check result streams
    result_pattern = f"{tenant_id}:*:results"
    for key in redis_client.scan_iter(match=result_pattern):
        key_str = key.decode() if isinstance(key, bytes) else key
        try:
            info = redis_client.xinfo_stream(key_str)
            all_streams.append({
                "stream": key_str,
                "length": info["length"],
                "type": "results"
            })
        except:
            pass
    
    if all_streams:
        print(f"Found {len(all_streams)} active streams:")
        print()
        for stream in sorted(all_streams, key=lambda x: x["stream"]):
            emoji = "📥" if stream["type"] == "tasks" else "📤"
            print(f"   {emoji} {stream['stream']}")
            print(f"      Messages: {stream['length']}")
        print()
    else:
        print("No active streams found")
        print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    print("✅ Manager delegation tools working correctly")
    print(f"✅ Leads stream created: {leads_stream}")
    print(f"✅ Outreach stream created: {outreach_stream}")
    print()
    print("📋 NEXT STEPS:")
    print()
    print("1. Start Leads Consumer:")
    print("   python agent/orchestrators/leads_orchestrator/consumer.py")
    print()
    print("2. Start Outreach Consumer:")
    print("   python agent/orchestrators/outreach_orchestrator/consumer.py")
    print()
    print("3. Consumers will:")
    print("   - Create consumer groups automatically")
    print("   - Process tasks from streams")
    print("   - Publish results to result streams")
    print()
    print("4. Check results with:")
    print(f"   delegation.check_task_status('{result['task_id']}')")
    print()
    print("=" * 80)


if __name__ == "__main__":
    try:
        test_stream_setup()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
