#!/usr/bin/env python
"""Test the _build_inbound_email_steps routing logic."""
import sys
sys.path.insert(0, ".")

from tiers.tier_2.leads_orchestrator.leads_orchestrator import LeadsOrchestrator

# Initialize orchestrator
orch = LeadsOrchestrator("test-tenant")

# Test case 1: No lead resolution (should go to staging_new)
email_event = {
    "from": "test@example.com",
    "to": "support@company.com",
    "subject": "Test email",
    "body": "Hello",
    "thread_id": "thread123",
    "message_id": "msg123",
}

# Case 1: No lead_resolution (default)
print("=== Case 1: No lead_resolution ===")
steps = orch._build_inbound_email_steps(
    email_event=email_event,
    lead_data={},
    cleanup_staging=False,
    lead_resolution=None,
)
for s in steps:
    print(f"  {s['step_name']}: table={s['table']}, op={s['operation']}")

# Case 2: lead_resolution with lead_source=None (RAG not found)
print("\n=== Case 2: lead_source=None (RAG not found) ===")
steps = orch._build_inbound_email_steps(
    email_event=email_event,
    lead_data={},
    cleanup_staging=False,
    lead_resolution={"lead_source": None, "lead_id": None, "status": "not_found"},
)
for s in steps:
    print(f"  {s['step_name']}: table={s['table']}, op={s['operation']}")

# Case 3: lead_resolution with lead_source="leads" (found in leads table)
print("\n=== Case 3: lead_source='leads' with lead_id ===")
steps = orch._build_inbound_email_steps(
    email_event=email_event,
    lead_data={},
    cleanup_staging=False,
    lead_resolution={"lead_source": "leads", "lead_id": "uuid-123"},
)
for s in steps:
    print(f"  {s['step_name']}: table={s['table']}, op={s['operation']}")

# Case 4: lead_resolution with source="rag_not_found" (no lead_source key)
print("\n=== Case 4: source='rag_not_found' (what reply_packet shows) ===")
steps = orch._build_inbound_email_steps(
    email_event=email_event,
    lead_data={},
    cleanup_staging=False,
    lead_resolution={"source": "rag_not_found", "lead_id": None, "status": "unknown"},
)
for s in steps:
    print(f"  {s['step_name']}: table={s['table']}, op={s['operation']}")
