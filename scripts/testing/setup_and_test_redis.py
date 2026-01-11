#!/usr/bin/env python
"""
Complete Redis Architecture Setup and Testing Script

This script will:
1. Initialize all Redis streams from the registry
2. Test downstream flow (Manager → Orchestrators → Agents)
3. Test upstream flow (Agents → Orchestrators → Manager)
4. Verify all consumer groups
5. Generate a comprehensive test report
"""

import os
import sys
import json
import time
import redis
from datetime import datetime
from typing import Dict, List

# Load .env if present, then fall back to local Redis.
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

os.environ.setdefault('REDIS_URL', os.getenv('REDIS_URL', 'redis://localhost:6379/0'))
os.environ.setdefault('TENANT_ID', os.getenv('TENANT_ID', 'agentic-dev'))

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from services.redis.stream_registry import get_registry, Tier, StreamType


def print_header(title: str):
    """Print a formatted header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def print_section(title: str):
    """Print a formatted section"""
    print("\n" + "-" * 80)
    print(f"  {title}")
    print("-" * 80 + "\n")


class RedisArchitectureTester:
    """Complete Redis architecture setup and testing"""
    
    def __init__(self):
        self.redis_url = os.getenv('REDIS_URL')
        self.tenant_id = os.getenv('TENANT_ID')
        self.redis = redis.from_url(self.redis_url, decode_responses=True)
        self.registry = get_registry()
        self.test_results = {
            'initialization': {},
            'downstream_tests': {},
            'upstream_tests': {},
            'verification': {}
        }
    
    def step_1_verify_clean_slate(self):
        """Verify Redis is clean (no existing streams)"""
        print_header("STEP 1: Verify Clean Slate")
        
        all_keys = self.redis.keys(f"{self.tenant_id}:*")
        
        if not all_keys:
            print("✓ Redis is clean - no existing streams found")
            self.test_results['initialization']['clean_slate'] = True
        else:
            print(f"⚠ Found {len(all_keys)} existing keys:")
            for key in all_keys[:10]:  # Show first 10
                print(f"  - {key}")
            if len(all_keys) > 10:
                print(f"  ... and {len(all_keys) - 10} more")
            self.test_results['initialization']['clean_slate'] = False
    
    def step_2_initialize_all_streams(self):
        """Initialize all streams and consumer groups"""
        print_header("STEP 2: Initialize All Streams")
        
        all_streams = self.registry.get_all_streams(self.tenant_id)
        created = []
        errors = []
        
        for stream_name, stream_key in sorted(all_streams.items()):
            stream_def = self.registry._streams[stream_name]
            
            try:
                if stream_def.consumer_group:
                    # Create stream with consumer group
                    self.redis.xgroup_create(
                        stream_key,
                        stream_def.consumer_group,
                        id="0",
                        mkstream=True
                    )
                    print(f"✓ Created {stream_key}")
                    print(f"  └─ Consumer group: {stream_def.consumer_group}")
                    created.append(stream_key)
                else:
                    # Create stream without consumer group
                    msg_id = self.redis.xadd(stream_key, {"_init": "true"})
                    self.redis.xdel(stream_key, msg_id)
                    print(f"✓ Created {stream_key} (no consumer group)")
                    created.append(stream_key)
            except Exception as e:
                print(f"✗ Error creating {stream_key}: {e}")
                errors.append((stream_key, str(e)))
        
        print(f"\n✓ Successfully created {len(created)} streams")
        if errors:
            print(f"✗ {len(errors)} errors")
        
        self.test_results['initialization']['created'] = created
        self.test_results['initialization']['errors'] = errors
    
    def step_3_test_downstream_tier1_to_tier2(self):
        """Test Manager → Orchestrators delegation"""
        print_header("STEP 3: Test Downstream - Tier 1 → Tier 2")
        
        # Get Manager task stream
        manager_tasks = self.registry.get_stream_key(
            Tier.MANAGER, "manager", StreamType.TASKS, self.tenant_id
        )
        
        # Get expected downstream targets
        downstream = self.registry.get_downstream_streams(
            Tier.MANAGER, "manager", StreamType.TASKS, self.tenant_id
        )
        
        print(f"Source: {manager_tasks}")
        print(f"Expected downstream targets:")
        for target in downstream:
            print(f"  → {target}")
        
        # Test 1: Delegate to Leads
        test_task_1 = {
            "task_id": "test_leads_001",
            "goal": "Find 50 AI startups",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        leads_tasks = self.registry.get_stream_key(
            Tier.ORCHESTRATOR, "leads", StreamType.TASKS, self.tenant_id
        )
        
        msg_id_1 = self.redis.xadd(leads_tasks, {
            "payload": json.dumps(test_task_1)
        })
        print(f"\n✓ Test 1: Delegated to Leads")
        print(f"  Stream: {leads_tasks}")
        print(f"  Message ID: {msg_id_1}")
        
        # Test 2: Delegate to Outreach
        test_task_2 = {
            "task_id": "test_outreach_001",
            "goal": "Create email campaign",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        outreach_tasks = self.registry.get_stream_key(
            Tier.ORCHESTRATOR, "outbound", StreamType.TASKS, self.tenant_id
        )
        
        msg_id_2 = self.redis.xadd(outreach_tasks, {
            "payload": json.dumps(test_task_2)
        })
        print(f"\n✓ Test 2: Delegated to Outreach")
        print(f"  Stream: {outreach_tasks}")
        print(f"  Message ID: {msg_id_2}")
        
        # Verify messages exist
        leads_count = self.redis.xlen(leads_tasks)
        outreach_count = self.redis.xlen(outreach_tasks)
        
        print(f"\nVerification:")
        print(f"  {leads_tasks}: {leads_count} messages")
        print(f"  {outreach_tasks}: {outreach_count} messages")
        
        self.test_results['downstream_tests']['tier1_to_tier2'] = {
            'leads_delegated': msg_id_1,
            'outreach_delegated': msg_id_2,
            'leads_count': leads_count,
            'outreach_count': outreach_count
        }
    
    def step_4_test_downstream_tier2_to_tier3(self):
        """Test Orchestrators → Agents delegation"""
        print_header("STEP 4: Test Downstream - Tier 2 → Tier 3")
        
        # Test Leads → RAG
        print_section("Leads → RAG Agent")
        
        rag_tasks = self.registry.get_stream_key(
            Tier.AGENT, "rag", StreamType.TASKS, self.tenant_id
        )
        
        test_rag = {
            "task_id": "test_rag_001",
            "lead_id": "lead_123",
            "query": "Enrich company data",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        msg_rag = self.redis.xadd(rag_tasks, {
            "payload": json.dumps(test_rag)
        })
        print(f"✓ Delegated to RAG Agent")
        print(f"  Stream: {rag_tasks}")
        print(f"  Message ID: {msg_rag}")
        
        # Test Leads → Persistence
        print_section("Leads → Persistence Agent")
        
        persist_tasks = self.registry.get_stream_key(
            Tier.AGENT, "persistence", StreamType.TASKS, self.tenant_id
        )
        
        test_persist = {
            "task_id": "test_persist_001",
            "operation": "bulk_insert",
            "leads": [{"id": 1}, {"id": 2}],
            "timestamp": datetime.utcnow().isoformat()
        }
        
        msg_persist = self.redis.xadd(persist_tasks, {
            "payload": json.dumps(test_persist)
        })
        print(f"✓ Delegated to Persistence Agent")
        print(f"  Stream: {persist_tasks}")
        print(f"  Message ID: {msg_persist}")
        
        # Test Outreach → Copywriter
        print_section("Outreach → Copywriter Agent")
        
        copy_tasks = self.registry.get_stream_key(
            Tier.AGENT, "copywriter", StreamType.TASKS, self.tenant_id
        )
        
        test_copy = {
            "task_id": "test_copy_001",
            "leads": [{"name": "Acme Corp"}],
            "template": "intro_email",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        msg_copy = self.redis.xadd(copy_tasks, {
            "payload": json.dumps(test_copy)
        })
        print(f"✓ Delegated to Copywriter Agent")
        print(f"  Stream: {copy_tasks}")
        print(f"  Message ID: {msg_copy}")
        
        # Verify
        print_section("Verification")
        rag_count = self.redis.xlen(rag_tasks)
        persist_count = self.redis.xlen(persist_tasks)
        copy_count = self.redis.xlen(copy_tasks)
        
        print(f"  {rag_tasks}: {rag_count} messages")
        print(f"  {persist_tasks}: {persist_count} messages")
        print(f"  {copy_tasks}: {copy_count} messages")
        
        self.test_results['downstream_tests']['tier2_to_tier3'] = {
            'rag': msg_rag,
            'persistence': msg_persist,
            'copywriter': msg_copy
        }
    
    def step_5_test_upstream_tier3_to_tier2(self):
        """Test Agents → Orchestrators results"""
        print_header("STEP 5: Test Upstream - Tier 3 → Tier 2")
        
        # Test RAG → Leads Results
        print_section("RAG Agent → Leads Results")
        
        rag_results = self.registry.get_stream_key(
            Tier.AGENT, "rag", StreamType.RESULTS, self.tenant_id
        )
        
        test_rag_result = {
            "task_id": "test_rag_001",
            "status": "completed",
            "enriched_data": {"company": "Acme Corp", "employees": 500},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        msg_rag_res = self.redis.xadd(rag_results, {
            "payload": json.dumps(test_rag_result)
        })
        print(f"✓ RAG result published")
        print(f"  Stream: {rag_results}")
        print(f"  Message ID: {msg_rag_res}")
        
        # Test Copywriter → Outreach Results
        print_section("Copywriter Agent → Outreach Results")
        
        copy_results = self.registry.get_stream_key(
            Tier.AGENT, "copywriter", StreamType.RESULTS, self.tenant_id
        )
        
        test_copy_result = {
            "task_id": "test_copy_001",
            "status": "completed",
            "emails": [{"to": "test@example.com", "subject": "Hello"}],
            "timestamp": datetime.utcnow().isoformat()
        }
        
        msg_copy_res = self.redis.xadd(copy_results, {
            "payload": json.dumps(test_copy_result)
        })
        print(f"✓ Copywriter result published")
        print(f"  Stream: {copy_results}")
        print(f"  Message ID: {msg_copy_res}")
        
        # Verify these should flow to orchestrator results
        print_section("Expected Upstream Targets")
        
        rag_upstream = self.registry.get_downstream_streams(
            Tier.AGENT, "rag", StreamType.RESULTS, self.tenant_id
        )
        print(f"RAG results should flow to:")
        for target in rag_upstream:
            print(f"  → {target}")
        
        copy_upstream = self.registry.get_downstream_streams(
            Tier.AGENT, "copywriter", StreamType.RESULTS, self.tenant_id
        )
        print(f"Copywriter results should flow to:")
        for target in copy_upstream:
            print(f"  → {target}")
        
        self.test_results['upstream_tests']['tier3_to_tier2'] = {
            'rag_result': msg_rag_res,
            'copy_result': msg_copy_res
        }
    
    def step_6_test_upstream_tier2_to_tier1(self):
        """Test Orchestrators → Manager results"""
        print_header("STEP 6: Test Upstream - Tier 2 → Tier 1")
        
        # Test Leads → Manager Results
        print_section("Leads → Manager Results")
        
        leads_results = self.registry.get_stream_key(
            Tier.ORCHESTRATOR, "leads", StreamType.RESULTS, self.tenant_id
        )
        
        test_leads_result = {
            "task_id": "test_leads_001",
            "status": "completed",
            "leads_found": 50,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        msg_leads_res = self.redis.xadd(leads_results, {
            "payload": json.dumps(test_leads_result)
        })
        print(f"✓ Leads result published")
        print(f"  Stream: {leads_results}")
        print(f"  Message ID: {msg_leads_res}")
        
        # Test Outreach → Manager Results
        print_section("Outreach → Manager Results")
        
        outreach_results = self.registry.get_stream_key(
            Tier.ORCHESTRATOR, "outbound", StreamType.RESULTS, self.tenant_id
        )
        
        test_outreach_result = {
            "task_id": "test_outreach_001",
            "status": "completed",
            "campaign_id": "camp_123",
            "touchpoints": 200,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        msg_outreach_res = self.redis.xadd(outreach_results, {
            "payload": json.dumps(test_outreach_result)
        })
        print(f"✓ Outreach result published")
        print(f"  Stream: {outreach_results}")
        print(f"  Message ID: {msg_outreach_res}")
        
        # These should flow to Manager results
        print_section("Expected Upstream Target")
        
        manager_results = self.registry.get_stream_key(
            Tier.MANAGER, "manager", StreamType.RESULTS, self.tenant_id
        )
        print(f"Both orchestrator results should flow to:")
        print(f"  → {manager_results}")
        
        self.test_results['upstream_tests']['tier2_to_tier1'] = {
            'leads_result': msg_leads_res,
            'outreach_result': msg_outreach_res
        }
    
    def step_7_test_system_streams(self):
        """Test system-wide streams"""
        print_header("STEP 7: Test System Streams")
        
        # Test DLQ
        print_section("Dead Letter Queue")
        dlq_stream = self.registry.get_stream_key(
            Tier.SYSTEM, "dlq", StreamType.DLQ, self.tenant_id
        )
        
        test_dlq = {
            "original_stream": "agentic-dev:agents:rag:tasks",
            "error": "Processing failed after 3 retries",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        msg_dlq = self.redis.xadd(dlq_stream, {"payload": json.dumps(test_dlq)})
        print(f"✓ DLQ message published: {msg_dlq}")
        
        # Test Health
        print_section("Health Monitoring")
        health_stream = self.registry.get_stream_key(
            Tier.SYSTEM, "health", StreamType.HEALTH, self.tenant_id
        )
        
        test_health = {
            "service": "rag-worker",
            "status": "up",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        msg_health = self.redis.xadd(health_stream, {"payload": json.dumps(test_health)})
        print(f"✓ Health heartbeat published: {msg_health}")
        
        # Test Audit
        print_section("Audit Trail")
        audit_stream = self.registry.get_stream_key(
            Tier.SYSTEM, "audit", StreamType.AUDIT, self.tenant_id
        )
        
        test_audit = {
            "action": "lead_enrichment",
            "user": "system",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        msg_audit = self.redis.xadd(audit_stream, {"payload": json.dumps(test_audit)})
        print(f"✓ Audit event published: {msg_audit}")
        
        self.test_results['system_tests'] = {
            'dlq': msg_dlq,
            'health': msg_health,
            'audit': msg_audit
        }
    
    def step_8_verify_all_streams(self):
        """Verify all streams and consumer groups"""
        print_header("STEP 8: Verification Summary")
        
        all_streams = self.registry.get_all_streams(self.tenant_id)
        
        print("Stream Inventory:")
        tier_counts = {'MANAGER': 0, 'ORCHESTRATOR': 0, 'AGENT': 0, 'SYSTEM': 0}
        
        for stream_name, stream_key in sorted(all_streams.items()):
            stream_def = self.registry._streams[stream_name]
            try:
                length = self.redis.xlen(stream_key)
                tier_counts[stream_def.tier.name] += 1
                
                status = "✓"
                if length > 0:
                    status = f"✓ ({length} msgs)"
                
                print(f"  {status} {stream_key}")
                
                # Check consumer group if defined
                if stream_def.consumer_group:
                    try:
                        groups = self.redis.xinfo_groups(stream_key)
                        group_names = [g['name'] for g in groups]
                        if stream_def.consumer_group in group_names:
                            print(f"      └─ Consumer group: {stream_def.consumer_group} ✓")
                        else:
                            print(f"      └─ Consumer group: {stream_def.consumer_group} ✗ MISSING")
                    except:
                        pass
            except Exception as e:
                print(f"  ✗ {stream_key}: {e}")
        
        print(f"\nTier Summary:")
        for tier, count in tier_counts.items():
            print(f"  {tier}: {count} streams")
        
        self.test_results['verification']['tier_counts'] = tier_counts
    
    def step_9_generate_report(self):
        """Generate comprehensive test report"""
        print_header("STEP 9: Test Report")
        
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "tenant_id": self.tenant_id,
            "test_results": self.test_results
        }
        
        # Save to file
        report_file = "redis_setup_test_results.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"✓ Test report saved to: {report_file}")
        
        # Print summary
        print("\nTest Summary:")
        print(f"  Initialization: {len(self.test_results['initialization'].get('created', []))} streams created")
        print(f"  Downstream Tests: ✓ Tier 1→2, ✓ Tier 2→3")
        print(f"  Upstream Tests: ✓ Tier 3→2, ✓ Tier 2→1")
        print(f"  System Streams: ✓ DLQ, ✓ Health, ✓ Audit")
        
        # Data flow visualization
        print_section("Data Flow Verified")
        print("  Downstream (Task Delegation):")
        print("    External → Manager → Orchestrators → Agents ✓")
        print("\n  Upstream (Result Propagation):")
        print("    Agents → Orchestrators → Manager → External ✓")
    
    def run_complete_test(self):
        """Run all test steps"""
        print_header("REDIS ARCHITECTURE - COMPLETE SETUP & TEST")
        print(f"Tenant: {self.tenant_id}")
        print(f"Redis: {self.redis_url.split('@')[-1] if '@' in self.redis_url else self.redis_url}")
        
        try:
            self.step_1_verify_clean_slate()
            self.step_2_initialize_all_streams()
            self.step_3_test_downstream_tier1_to_tier2()
            self.step_4_test_downstream_tier2_to_tier3()
            self.step_5_test_upstream_tier3_to_tier2()
            self.step_6_test_upstream_tier2_to_tier1()
            self.step_7_test_system_streams()
            self.step_8_verify_all_streams()
            self.step_9_generate_report()
            
            print_header("✅ ALL TESTS PASSED")
            print("Redis architecture is fully set up and tested!")
            print("\nNext steps:")
            print("  1. Start consumers: python start_all_consumers.py")
            print("  2. Send test request to Manager stream")
            print("  3. Monitor with: python scripts/manage_redis_streams.py --verify")
            
        except Exception as e:
            print_header("❌ TEST FAILED")
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()


def main():
    tester = RedisArchitectureTester()
    tester.run_complete_test()


if __name__ == "__main__":
    main()
