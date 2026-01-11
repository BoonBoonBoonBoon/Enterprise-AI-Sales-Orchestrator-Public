#!/usr/bin/env python
"""
Test script for RAG Agent enrichment pipeline.

Sends 1-3 mock lead enrichment tasks to the RAG agent via Redis.
Demonstrates:
- Validation-first execution (completeness scoring)
- Deterministic path (valid data, ≥0.7 completeness)
- LLM repair fallback (partial data, 0.3-0.7 completeness)
- Error path (hopeless data, <0.3 completeness)

Usage:
    python scripts/test_rag_enrichment.py --examples 3
    python scripts/test_rag_enrichment.py --wait  # Wait for results
"""

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root to path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

# Load environment
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

try:
    from services.redis import RedisPubSub
except ImportError:
    from services.redis import RedisStreamsClient as RedisPubSub

from core.envelope import task as create_task_envelope, from_redis_message, to_redis_fields


class RAGEnrichmentTester:
    """Test harness for RAG agent enrichment tasks."""
    
    def __init__(self, tenant_id: str = "agentic-dev"):
        self.tenant_id = tenant_id
        self.redis_client = RedisPubSub().client
        self.task_stream = f"{tenant_id}:agents:rag:tasks"
        self.result_stream = f"{tenant_id}:agents:rag:results"
        
    def send_task(self, entity_type: str, payload: Dict[str, Any], description: str = "", table: str = "") -> str:
        """Send enrichment task to RAG agent."""
        task_id = str(uuid.uuid4())
        
        # Create task envelope
        envelope = create_task_envelope(
            source="test_script",
            task_id=task_id,
            destination=self.task_stream,
            payload={
                "goal": f"Enrich {entity_type} entity from {table}",
                "entity_type": entity_type,
                "table": table,  # Specify which table this lead comes from
                "record": payload,
                "include_vector_search": True,
                "include_external_apis": True
            }
        )
        
        # Send to Redis stream
        msg_id = self.redis_client.xadd(
            self.task_stream,
            to_redis_fields(envelope)
        )
        
        print(f"\n{'='*70}")
        print(f"📤 Task Sent: {description}")
        print(f"{'='*70}")
        print(f"Task ID: {task_id}")
        print(f"Message ID: {msg_id.decode() if isinstance(msg_id, bytes) else msg_id}")
        print(f"Entity Type: {entity_type}")
        print(f"Table: {table}")
        print(f"Lead Email: {payload.get('email', 'N/A')}")
        print(f"Lead Name: {payload.get('first_name', '')} {payload.get('last_name', '')}".strip())
        print(f"Company: {payload.get('company_name', 'N/A')}")
        print(f"Stream: {self.task_stream}")
        
        return task_id
    
    def wait_for_result(self, task_id: str, timeout: int = 30) -> Optional[Dict[str, Any]]:
        """Wait for and retrieve result from RAG agent."""
        print(f"\n⏳ Waiting for result (timeout: {timeout}s)...")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Read latest messages from result stream
                messages = self.redis_client.xrevrange(
                    self.result_stream,
                    count=10
                )
                
                if messages:
                    # Check for our task ID in results
                    for msg_id, fields in messages:
                        try:
                            result_env = from_redis_message(fields)
                            if result_env.metadata.get("original_task_id") == task_id or \
                               result_env.metadata.get("task_id") == task_id:
                                return result_env.to_dict()
                        except Exception:
                            continue
                
                time.sleep(1)
            except Exception as e:
                print(f"Error waiting for result: {e}")
                time.sleep(1)
        
        print(f"❌ Timeout waiting for result (task_id={task_id})")
        return None
    
    def display_result(self, result: Dict[str, Any]):
        """Display enrichment result."""
        if not result:
            return
        
        print(f"\n{'='*70}")
        print(f"📥 Result Received")
        print(f"{'='*70}")
        
        metadata = result.get("metadata", {})
        payload = result.get("payload", {})
        
        print(f"Status: {result.get('status', 'UNKNOWN')}")
        print(f"Source: {metadata.get('source', 'N/A')}")
        print(f"Retrieved At: {metadata.get('retrieved_at', 'N/A')}")
        
        # Display validation results if present
        if "validation_result" in payload:
            val = payload["validation_result"]
            print(f"\n✅ Validation:")
            print(f"   Completeness Score: {val.get('completeness_score', 0):.2f}")
            print(f"   Valid: {val.get('is_valid', False)}")
            print(f"   Can Use Deterministic: {val.get('can_use_deterministic', False)}")
            print(f"   Needs Repair: {val.get('needs_repair', False)}")
            if val.get('missing_required_fields'):
                print(f"   Missing Fields: {val.get('missing_required_fields')}")
        
        # Display enrichment results if present
        if "enriched_data" in payload:
            enriched = payload["enriched_data"]
            print(f"\n🔍 Enrichment Results:")
            print(f"   Confidence: {enriched.get('confidence', 0):.2f}")
            print(f"   Sources: {enriched.get('sources', [])}")
            if enriched.get("data"):
                print(f"   Data: {json.dumps(enriched['data'], indent=4)[:200]}...")
        
        # Display repair results if present
        if "repair_result" in payload:
            repair = payload["repair_result"]
            print(f"\n🔧 Repair Results:")
            print(f"   Strategy: {repair.get('repair_strategy', 'none')}")
            print(f"   Confidence: {repair.get('confidence', 0):.2f}")
            print(f"   Repaired Fields: {repair.get('repaired_fields', [])}")
        
        # Display error if present
        if result.get("error"):
            print(f"\n❌ Error: {result['error']}")
        
        print(f"{'='*70}\n")


def create_test_cases() -> Dict[str, Dict[str, Any]]:
    """Create test cases from real Supabase leads data + variations."""
    
    # Real lead from Supabase (chris.wilson@wilson.com)
    real_lead_1 = {
        "id": "06b92f5b-9fb0-4977-a839-26f812f1bbcb",
        "client_id": "90fd5909-89fb-4a7f-afa9-d17810496768",
        "campaign_id": "9646f98a-e987-4a8c-b786-9b82ea985d38",
        "email": "chris.wilson@wilson.com",
        "first_name": "chris",
        "last_name": "wilson",
        "company_name": "Wilson C Holdings",
        "job_title": "Head of Operations",
        "phone_number": "07847200331",
        "current_status": "new",
        "sequence_step": 3,
        "sequence_active": False,
        "next_action_date": "2025-12-27T21:37:01+00:00",
        "last_contact_date": "2025-10-13T21:37:01+00:00",
        "booking_status": "not_booked",
        "re_engagement_date": "2026-01-16T21:37:01+00:00",
        "created_at": "2025-10-16T21:37:01+00:00",
        "updated_at": "2025-10-16T21:37:02.274212+00:00"
    }
    
    # Real lead from Supabase (jordan.brown@brown.com)
    real_lead_2 = {
        "id": "11b94092-f93b-4414-923c-5e69cbe19594",
        "client_id": "4ecd445c-1ff8-44a3-8a0c-404e7c69f031",
        "campaign_id": "9646f98a-e987-4a8c-b786-9b82ea985d38",
        "email": "jordan.brown@brown.com",
        "first_name": "jordan",
        "last_name": "brown",
        "company_name": "Brown J Limited",
        "job_title": "Founder",
        "phone_number": "07077473866",
        "current_status": "new",
        "sequence_step": 4,
        "sequence_active": False,
        "next_action_date": "2025-10-25T21:40:30+00:00",
        "last_contact_date": "2025-10-14T21:40:30+00:00",
        "booking_status": "not_booked",
        "re_engagement_date": "2026-03-26T21:40:30+00:00",
        "created_at": "2025-10-16T21:40:30+00:00",
        "updated_at": "2025-10-16T21:40:32.896492+00:00"
    }
    
    # Real lead from Supabase (alex.taylor@taylor.com)
    real_lead_3 = {
        "id": "13d390e6-567c-4c1b-9a17-1de85b24a8fe",
        "client_id": "592c9b4c-77be-4303-ad46-1ffb1ede127e",
        "campaign_id": "9646f98a-e987-4a8c-b786-9b82ea985d38",
        "email": "alex.taylor@taylor.com",
        "first_name": "alex",
        "last_name": "taylor",
        "company_name": "Taylor A Services",
        "job_title": "Director",
        "phone_number": "07488318262",
        "current_status": "new",
        "sequence_step": 2,
        "sequence_active": True,
        "next_action_date": "2025-10-31T16:48:18+00:00",
        "last_contact_date": "2025-09-27T16:48:18+00:00",
        "booking_status": "not_booked",
        "re_engagement_date": "2026-04-09T16:48:18+00:00",
        "created_at": "2025-10-18T16:48:18+00:00",
        "updated_at": "2025-10-18T16:48:26.113402+00:00"
    }
    
    # Fake lead 1: Based on real_lead_1 structure but fake data
    fake_lead_1 = {
        "id": str(uuid.uuid4()),
        "client_id": str(uuid.uuid4()),
        "campaign_id": "9646f98a-e987-4a8c-b786-9b82ea985d38",
        "email": "sarah.martinez@techventures.com",
        "first_name": "Sarah",
        "last_name": "Martinez",
        "company_name": "TechVentures Inc",
        "job_title": "VP Product",
        "phone_number": "07912345678",
        "current_status": "new",
        "sequence_step": 1,
        "sequence_active": True,
        "next_action_date": "2025-12-01T10:00:00+00:00",
        "last_contact_date": "2025-11-20T10:00:00+00:00",
        "booking_status": "not_booked",
        "re_engagement_date": "2026-02-15T10:00:00+00:00",
        "created_at": "2025-11-23T10:00:00+00:00",
        "updated_at": "2025-11-23T10:00:00+00:00"
    }
    
    # Fake lead 2: Partial data (missing last_name and company_name)
    fake_lead_2 = {
        "id": str(uuid.uuid4()),
        "client_id": str(uuid.uuid4()),
        "campaign_id": "9646f98a-e987-4a8c-b786-9b82ea985d38",
        "email": "michael.chen@company.io",
        "first_name": "Michael",
        # Missing: last_name
        # Missing: company_name
        "job_title": "CTO",
        "phone_number": "07634567890",
        "current_status": "new",
        "sequence_step": 2,
        "sequence_active": False,
        "next_action_date": "2025-11-30T14:00:00+00:00",
        "created_at": "2025-11-23T10:00:00+00:00",
        "updated_at": "2025-11-23T10:00:00+00:00"
    }
    
    # Fake lead 3: Hopeless (only minimal data)
    fake_lead_3 = {
        "id": str(uuid.uuid4()),
        # Missing: client_id (REQUIRED)
        # Missing: email, first_name, last_name, company_name, job_title
        "current_status": "new",
        "created_at": "2025-11-23T10:00:00+00:00"
    }
    
    return {
        "real_lead_1": {
            "description": "✅ REAL: chris.wilson from public.leads (Supabase)",
            "entity_type": "lead",
            "table": "public.leads",
            "payload": real_lead_1
        },
        "real_lead_2": {
            "description": "✅ REAL: jordan.brown from public.leads (Supabase)",
            "entity_type": "lead",
            "table": "public.leads",
            "payload": real_lead_2
        },
        "real_lead_3": {
            "description": "✅ REAL: alex.taylor from public.leads (Supabase)",
            "entity_type": "lead",
            "table": "public.leads",
            "payload": real_lead_3
        },
        "fake_lead_1": {
            "description": "✅ FAKE: sarah.martinez - Complete lead (≥0.7 completeness)",
            "entity_type": "lead",
            "table": "public.leads",
            "payload": fake_lead_1
        },
        "fake_lead_2": {
            "description": "🔧 FAKE: michael.chen - Partial lead (0.3-0.7 completeness, needs repair)",
            "entity_type": "lead",
            "table": "public.leads",
            "payload": fake_lead_2
        },
        "fake_lead_3": {
            "description": "❌ FAKE: hopeless - Severely incomplete (<0.3 completeness)",
            "entity_type": "lead",
            "table": "public.leads",
            "payload": fake_lead_3
        }
    }


def main():
    """Main test flow."""
    parser = argparse.ArgumentParser(description="Test RAG agent enrichment pipeline")
    parser.add_argument(
        "--examples",
        type=int,
        default=3,
        choices=[1, 2, 3, 4, 5, 6],
        help="Number of test examples to send (1-6: 3 real + 3 fake)"
    )
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Wait for results from RAG agent"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Result wait timeout (seconds)"
    )
    parser.add_argument(
        "--tenant",
        default="agentic-dev",
        help="Tenant ID for task streams"
    )
    parser.add_argument(
        "--real-only",
        action="store_true",
        help="Send only real leads from Supabase"
    )
    
    args = parser.parse_args()
    
    # Initialize tester
    tester = RAGEnrichmentTester(tenant_id=args.tenant)
    
    # Get test cases
    test_cases = create_test_cases()
    
    if args.real_only:
        test_names = ["real_lead_1", "real_lead_2", "real_lead_3"]
    else:
        # Default: use requested number of examples
        all_names = ["real_lead_1", "real_lead_2", "real_lead_3", "fake_lead_1", "fake_lead_2", "fake_lead_3"]
        test_names = all_names[:args.examples]
    
    print(f"""
╔════════════════════════════════════════════════════════════════════╗
║  RAG Agent Enrichment Test - Supabase Leads Data                   ║
╚════════════════════════════════════════════════════════════════════╝

Configuration:
  Tenant ID: {args.tenant}
  Examples: {len(test_names)} ({', '.join(test_names)})
  Wait for Results: {args.wait}
  Timeout: {args.timeout}s
  
Testing Supabase access and Redis processing:
  ✅ 3 real leads from public.leads table (READ test)
  ✅ 3 fake leads to test validation & repair (WRITE/enrichment test)
  🔧 LLM repair fallback on partial data
  ❌ Error path on hopeless data
  
Expected behaviors:
  - RAG agent queries Supabase to find existing leads
  - Validation scores completeness for enrichment routing
  - Redis handles all message passing and acknowledgments
""")
    
    # Send tasks
    task_ids = []
    for test_name in test_names:
        test_case = test_cases[test_name]
        task_id = tester.send_task(
            entity_type=test_case["entity_type"],
            payload=test_case["payload"],
            description=test_case["description"],
            table=test_case.get("table", "public.leads")
        )
        task_ids.append(task_id)
        time.sleep(1)  # Slight delay between sends
    
    # Wait for results if requested
    if args.wait:
        print(f"\n{'='*70}")
        print(f"Waiting for RAG agent results...")
        print(f"{'='*70}")
        
        for i, task_id in enumerate(task_ids, 1):
            result = tester.wait_for_result(task_id, timeout=args.timeout)
            if result:
                tester.display_result(result)
            else:
                print(f"\nℹ️  No result received for task {i} (task_id={task_id})")
                print(f"   Note: The RAG agent may still be processing.")
                print(f"   Check logs or manually query results stream: {tester.result_stream}")
    else:
        print(f"\n{'='*70}")
        print(f"Tasks enqueued successfully!")
        print(f"{'='*70}")
        print(f"\nTask IDs sent ({len(task_ids)} total):")
        for i, task_id in enumerate(task_ids, 1):
            test_name = test_names[i-1]
            test_case = test_cases[test_name]
            print(f"  {i}. {test_case['description']}")
            print(f"     Task ID: {task_id}")
        print(f"\nTo wait for results, run with --wait flag:")
        print(f"  python scripts/test_rag_enrichment.py --examples {args.examples} --wait")
        print(f"\nTo test only real Supabase leads:")
        print(f"  python scripts/test_rag_enrichment.py --real-only --wait")
        print(f"\nOr check result stream manually:")
        print(f"  redis-cli XREVRANGE {tester.result_stream} COUNT 10")
    
    print(f"\n{'='*70}\n")


if __name__ == "__main__":
    main()
