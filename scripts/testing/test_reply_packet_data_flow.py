#!/usr/bin/env python3
"""
Test script to verify data propagation through the reply packet chain.

This simulates the flow:
  RAG Agent → Leads Orchestrator → Outreach Orchestrator → Copywriter Agent

Using real lead data to verify all fields are correctly propagated.
"""

import asyncio
import sys
from pathlib import Path

# Ensure project root is in path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from core.schemas.reply_packet import ReplyPacket, LeadResolution, ConversationSummary, Facts, ActionsTaken, NextStep


def simulate_rag_response() -> dict:
    """Simulate what RAG returns after querying the leads table."""
    # This is the actual lead data from the database (as user shared)
    return {
        "status": "success",
        "lead": {
            "id": "22c9e838-8f52-4da2-8392-ffc724c193c2",
            "client_id": "93d28de3-2835-52f3-b2ef-c2eb8a2ac09b",
            "campaign_id": "9646f98a-e987-4a8c-b786-9b82ea985d38",
            "source": "inbound_email",
            "email": "test_write01@example.com",
            "first_name": "john",
            "last_name": "reed",
            "company_name": "jplm ltd",  # NOTE: DB uses company_name, not company
            "job_title": "Managing Sales Director",  # NOTE: DB uses job_title, not title
            "phone_number": None,
            "linkedin_url": None,
            "website_url": None,
            "location": None,
            "industry": "Wholesale appliances.",
            "company_size": "30+",
            "revenue_range": None,
            "raw_data": None,
            "duplicate_check_hash": None,
            "error_log": None,
            "enrichment_status": "pending",
            "qualification_status": "unqualified",
            "promotion_ready": False,
            "created_at": "2026-01-13 21:15:15.588757+00",
            "updated_at": "2026-01-13 21:15:15.588757+00",
            "archived_at": None,
        },
        "lead_source": "leads",
        "match_reason": "email_exact",
        "conversations": [],
        "messages": [],
        "query_trace": {
            "operation": "get_lead_context",
            "final_status": "success",
            "primary_table_hit": "leads",
            "fallback_used": False,
        },
    }


def simulate_email_event() -> dict:
    """Simulate the inbound email event."""
    return {
        "from": "test_write01@example.com",
        "from_name": "John Reed",
        "to": "sales@ourcompany.com",
        "subject": "Interest in your services",
        "text": "Hi, I saw your website and I'm interested in learning more about your offerings.",
        "thread_id": "thread-123",
        "message_id": "msg-456",
    }


def build_reply_packet_from_rag(rag_payload: dict, email_event: dict, goal: str) -> dict:
    """
    Simulate Leads Orchestrator building reply_packet from RAG result.
    
    This mirrors the logic in leads_orchestrator._build_reply_packet_from_rag()
    """
    lead_record = None
    conversations = []
    messages = []
    status = "unknown"
    lead_source = None
    query_trace = None
    match_reason = None

    if isinstance(rag_payload, dict):
        lead_record = rag_payload.get("lead")
        conversations = rag_payload.get("conversations") or []
        messages = rag_payload.get("messages") or []
        status = rag_payload.get("status", "unknown")
        lead_source = rag_payload.get("lead_source")
        query_trace = rag_payload.get("query_trace")
        match_reason = rag_payload.get("match_reason")

    lead_resolution = LeadResolution(
        status="found" if lead_record else status,
        lead_id=lead_record.get("id") if isinstance(lead_record, dict) else None,
        confidence=0.82 if lead_record else 0.25,
        source=lead_source if lead_source else ("rag" if lead_record else "rag_not_found"),
        alternatives=([{"match_reason": match_reason}] if match_reason else []),
        lead_data=lead_record if isinstance(lead_record, dict) else None,
    )

    convo_summary = ConversationSummary(
        recent_messages=messages[-10:] if isinstance(messages, list) else [],
    )

    # THIS IS THE FIX: Use correct DB column names
    facts = Facts(
        first_name=lead_record.get("first_name") if isinstance(lead_record, dict) else None,
        last_name=lead_record.get("last_name") if isinstance(lead_record, dict) else None,
        # DB column is 'company_name'; also check 'company' for backward compat
        company=(lead_record.get("company_name") or lead_record.get("company")) if isinstance(lead_record, dict) else None,
        # DB column is 'job_title'; also check 'title'/'role' for backward compat
        role=(lead_record.get("job_title") or lead_record.get("title") or lead_record.get("role")) if isinstance(lead_record, dict) else None,
        email=lead_record.get("email") if isinstance(lead_record, dict) else email_event.get("from"),
        intent=email_event.get("intent") or email_event.get("subject"),
        extras={
            "email_event_subject": email_event.get("subject"),
            "goal": goal,
            "match_reason": match_reason,
        },
    )

    actions_taken = ActionsTaken(
        stored=True,
        enriched=bool(lead_record or messages or conversations),
        writes=["test_persistence_task"],
    )

    next_step = NextStep(
        delegate_to=["outbound"],
        reason="reply_packet_ready_for_outreach",
    )

    packet = ReplyPacket(
        lead_resolution=lead_resolution,
        conversation=convo_summary,
        facts=facts,
        actions_taken=actions_taken,
        inbound_email_event=email_event,
        recommended_strategy="craft personalized reply using retrieved history",
        next=next_step,
        query_trace=query_trace,
    )

    return packet.dict()


async def test_copywriter_extraction(reply_packet: dict):
    """Test that Copywriter correctly extracts data from reply_packet."""
    from tiers.tier_3.copywriter_agent.copywriter import CopywriterAgent
    
    agent = CopywriterAgent()
    
    # Simulate the context that Outreach passes to Copywriter
    context = {
        "reply_packet": reply_packet,
    }
    
    inbound = reply_packet.get("inbound_email_event") or {}
    facts = reply_packet.get("facts") or {}
    lead_resolution = reply_packet.get("lead_resolution") or {}
    leads_result = {}  # In real flow, this might come from upstream
    
    # Test extraction methods
    recipient_name = agent._extract_recipient_name(inbound, facts, lead_resolution, leads_result)
    recipient_company = agent._extract_company(facts, lead_resolution, leads_result)
    recipient_role = agent._extract_role(facts, lead_resolution, leads_result)
    
    print("\n=== COPYWRITER EXTRACTION TEST ===")
    print(f"Recipient Name: {recipient_name}")
    print(f"Recipient Company: {recipient_company}")
    print(f"Recipient Role: {recipient_role}")
    
    # Verify values are correct
    assert recipient_name != "there", f"Expected real name, got: {recipient_name}"
    assert recipient_company is not None, "Company should not be None"
    assert recipient_role is not None, "Role should not be None"
    
    print("\n✅ All extractions successful!")
    print(f"  - Name: '{recipient_name}' (expected: 'John Reed' or 'john')")
    print(f"  - Company: '{recipient_company}' (expected: 'jplm ltd')")
    print(f"  - Role: '{recipient_role}' (expected: 'Managing Sales Director')")


def main():
    print("=" * 60)
    print("REPLY PACKET DATA FLOW TEST")
    print("=" * 60)
    
    # Step 1: Simulate RAG response
    print("\n[Step 1] Simulating RAG Agent response...")
    rag_response = simulate_rag_response()
    print(f"  RAG status: {rag_response['status']}")
    print(f"  Lead found: {rag_response['lead'] is not None}")
    print(f"  Lead source: {rag_response['lead_source']}")
    
    # Step 2: Simulate inbound email
    print("\n[Step 2] Simulating inbound email event...")
    email_event = simulate_email_event()
    print(f"  From: {email_event['from']}")
    print(f"  Subject: {email_event['subject']}")
    
    # Step 3: Build reply_packet (as Leads Orchestrator does)
    print("\n[Step 3] Building reply_packet from RAG result...")
    reply_packet = build_reply_packet_from_rag(
        rag_payload=rag_response,
        email_event=email_event,
        goal="handle inbound email reply",
    )
    
    # Print the reply_packet facts
    facts = reply_packet.get("facts", {})
    print(f"\n[Reply Packet - Facts]")
    print(f"  first_name: {facts.get('first_name')}")
    print(f"  last_name: {facts.get('last_name')}")
    print(f"  company: {facts.get('company')}")
    print(f"  role: {facts.get('role')}")
    print(f"  email: {facts.get('email')}")
    
    # Print lead_resolution.lead_data
    lead_resolution = reply_packet.get("lead_resolution", {})
    lead_data = lead_resolution.get("lead_data", {})
    print(f"\n[Reply Packet - LeadData]")
    print(f"  status: {lead_resolution.get('status')}")
    print(f"  lead_id: {lead_resolution.get('lead_id')}")
    print(f"  first_name: {lead_data.get('first_name') if lead_data else 'N/A'}")
    print(f"  company_name: {lead_data.get('company_name') if lead_data else 'N/A'}")
    print(f"  job_title: {lead_data.get('job_title') if lead_data else 'N/A'}")
    
    # Step 4: Test Copywriter extraction
    print("\n[Step 4] Testing Copywriter extraction...")
    asyncio.run(test_copywriter_extraction(reply_packet))
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED - Data flows correctly!")
    print("=" * 60)


if __name__ == "__main__":
    main()
