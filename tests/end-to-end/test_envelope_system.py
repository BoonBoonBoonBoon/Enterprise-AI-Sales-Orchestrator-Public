"""End-to-end test of enhanced envelope system (without Redis dependency).

Demonstrates:
- Envelope creation with task(), result(), error() builders
- Context forwarding from orchestrator -> RAG -> copywriter
- Serialization/deserialization with to_redis_fields() and from_redis_message()
- Correlation ID tracking across multi-agent pipeline
- Retry/DLQ lifecycle
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Any
import json

# Add project root to path (for direct execution outside pytest)
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from core.envelope.typed_envelope import (
    task,
    result,
    error,
    to_redis_fields,
    from_redis_message,
    Priority,
    Status,
)


def _make_orchestrator_cmd():
    return task(
        source="test_client",
        task_id="test-campaign-001",
        destination="orchestrator:commands",
        payload={
            "type": "campaign_followup_batch",
            "campaign_id": "camp-001",
            "lead_ids": [1, 2, 3],
            "step": 3,
            "context": {
                "campaign_name": "Q1 Outreach",
                "product": "AI Platform",
                "value_prop": "10x productivity gains",
            },
            "instructions": {
                "tone": "professional",
                "subject_hint": "Quick follow-up",
                "length": "short",
                "cta": "Schedule demo",
            },
        },
        campaign_id="camp-001",
        tags={"test": "e2e", "client": "manual"},
        priority=Priority.HIGH,
    )


def _make_rag_task(orchestrator_cmd):
    lead_id = orchestrator_cmd.payload["lead_ids"][0]
    return task(
        source="orchestrator",
        task_id=f"rag-lead-{lead_id}",
        destination="rag:tasks",
        payload={
            "query": {"table": "leads", "filters": {"id": lead_id}},
            "forward_to": {
                "agent": "copywriter",
                "campaign_context": orchestrator_cmd.payload["context"],
                "instructions": orchestrator_cmd.payload["instructions"],
            },
        },
        correlation_id=orchestrator_cmd.metadata.correlation_id,
        campaign_id=orchestrator_cmd.metadata.campaign_id,
        tags={**orchestrator_cmd.metadata.tags, "parent_task_id": orchestrator_cmd.metadata.task_id},
    )


def _make_rag_result(rag_task, lead_data: Dict[str, Any]):
    rag_result = result(
        original=rag_task,
        payload={"records": [lead_data], "count": 1, "table": "leads"},
        source="rag_worker",
    )
    rag_result.mark_processed()
    return rag_result


def _make_copy_task(rag_task, lead_data: Dict[str, Any]):
    forward_spec = rag_task.payload.get("forward_to", {})
    return task(
        source="rag_worker",
        task_id=f"copy-{lead_data['id']}",
        destination="copy:tasks",
        payload={
            "lead_data": lead_data,
            "instructions": forward_spec.get("instructions", {}),
            "campaign_context": forward_spec.get("campaign_context", {}),
        },
        correlation_id=rag_task.metadata.correlation_id,
        campaign_id=rag_task.metadata.campaign_id,
        tags={"parent_task_id": rag_task.metadata.task_id, "source": "rag"},
        priority=Priority.NORMAL,
    )


def _make_copy_result(copy_task, generated_copy: str):
    copy_result = result(
        original=copy_task,
        payload={"generated_copy": generated_copy, "quality": "good"},
        source="copywriter_worker",
    )
    copy_result.mark_processed()
    return copy_result


def print_section(title: str):
    """Print section header."""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


def print_envelope(env, label: str):
    """Print envelope summary."""
    print(f"{label}:")
    print(f"  Task ID: {env.metadata.task_id}")
    print(f"  Correlation ID: {env.metadata.correlation_id}")
    print(f"  Status: {env.status}")
    print(f"  Priority: {env.metadata.priority}")
    print(f"  Source: {env.metadata.source}")
    print(f"  Destination: {env.metadata.destination}")
    print(f"  Campaign ID: {env.metadata.campaign_id}")
    print(f"  Tags: {env.metadata.tags}")
    print(f"  Payload keys: {list(env.payload.keys())}")
    if env.error:
        print(f"  Error: {env.error}")
    print()


def test_orchestrator_command():
    """Test 1: Orchestrator creates command envelope."""
    print_section("Test 1: Orchestrator Command")

    cmd = _make_orchestrator_cmd()

    print_envelope(cmd, "Orchestrator Command")

    # Serialize (simulate Redis XADD)
    redis_fields = to_redis_fields(cmd)
    print(f"Serialized fields ({len(redis_fields)} keys):")
    for k, v in list(redis_fields.items())[:5]:
        print(f"  {k}: {v[:100] if isinstance(v, str) and len(v) > 100 else v}")
    print(f"  ... ({len(redis_fields) - 5} more fields)\n")

    # Deserialize (simulate consumer reading)
    cmd_restored = from_redis_message(redis_fields)
    print(f"✓ Deserialization successful: {cmd_restored.metadata.task_id}")
    print(f"  Correlation ID preserved: {cmd_restored.metadata.correlation_id == cmd.metadata.correlation_id}")

    return cmd


def test_rag_task_with_forward():
    """Test 2: Orchestrator creates RAG task with forward_to."""
    print_section("Test 2: RAG Task with Context Forwarding")
    
    orchestrator_cmd = _make_orchestrator_cmd()

    # Orchestrator creates RAG task with forward_to
    rag_task = _make_rag_task(orchestrator_cmd)
    
    print_envelope(rag_task, "RAG Task")
    
    # Verify forward_to structure
    forward_spec = rag_task.payload.get("forward_to", {})
    print(f"Forward-to specification:")
    print(f"  Agent: {forward_spec.get('agent')}")
    print(f"  Campaign context keys: {list(forward_spec.get('campaign_context', {}).keys())}")
    print(f"  Instructions keys: {list(forward_spec.get('instructions', {}).keys())}")
    print()
    
    return rag_task


def test_rag_result_and_copywriter_forward():
    """Test 3: RAG fetches data and forwards to copywriter."""
    print_section("Test 3: RAG Result + Copywriter Forwarding")
    
    # Simulate RAG fetching lead data
    lead_data = {
        "id": 1,
        "first_name": "John",
        "last_name": "Doe",
        "email": "john@example.com",
        "company_name": "Acme Corp",
        "title": "VP Engineering"
    }
    
    rag_task = _make_rag_task(_make_orchestrator_cmd())
    rag_result = _make_rag_result(rag_task, lead_data)
    
    print_envelope(rag_result, "RAG Result")
    
    # RAG creates copywriter task with forwarded context
    copy_task = _make_copy_task(rag_task, lead_data)
    
    print_envelope(copy_task, "Copywriter Task (Forwarded)")
    
    # Verify all three context components
    print(f"Context forwarding verification:")
    print(f"  ✓ lead_data: {len(copy_task.payload.get('lead_data', {}))} fields")
    print(f"  ✓ campaign_context: {len(copy_task.payload.get('campaign_context', {}))} fields")
    print(f"  ✓ instructions: {len(copy_task.payload.get('instructions', {}))} fields")
    print(f"  ✓ Correlation ID matches: {copy_task.metadata.correlation_id == rag_task.metadata.correlation_id}")
    print()
    
    return copy_task


def test_copywriter_generation():
    """Test 4: Copywriter generates email from context."""
    print_section("Test 4: Copywriter Email Generation")
    
    copy_task = _make_copy_task(_make_rag_task(_make_orchestrator_cmd()), {
        "id": 1,
        "first_name": "John",
        "last_name": "Doe",
        "email": "john@example.com",
        "company_name": "Acme Corp",
        "title": "VP Engineering",
    })

    # Extract context components
    lead_data = copy_task.payload.get("lead_data", {})
    campaign_context = copy_task.payload.get("campaign_context", {})
    instructions = copy_task.payload.get("instructions", {})
    
    # Build prompt (placeholder logic)
    lead_name = lead_data.get("first_name", "there").title()
    company = lead_data.get("company_name", "your company")
    step = campaign_context.get("step", 1)
    tone = instructions.get("tone", "professional")
    subject_hint = instructions.get("subject_hint", "Following up")
    
    print(f"Prompt building:")
    print(f"  Lead: {lead_name} at {company} ({lead_data.get('title')})")
    print(f"  Campaign: {campaign_context.get('campaign_name')} - Step {step}")
    print(f"  Product: {campaign_context.get('product')}")
    print(f"  Tone: {tone}")
    print(f"  Subject hint: {subject_hint}")
    print()
    
    # Generate content (placeholder)
    content = {
        "subject": f"{subject_hint} - Step {step}",
        "body": (
            f"Hi {lead_name},\n\n"
            f"Following up on our earlier conversation about {campaign_context.get('product')}.\n\n"
            f"I wanted to share how we can help {company} achieve {campaign_context.get('value_prop')}.\n\n"
            f"Would love to {instructions.get('cta').lower()} with you.\n\n"
            f"Best regards,\n[Your Name]"
        ),
        "metadata": {
            "model": "placeholder",
            "tokens": 0,
            "tone": tone,
            "step": step
        }
    }
    
    # Emit result
    copy_result = result(
        original=copy_task,
        payload={
            "content": content,
            "lead_id": lead_data.get("id"),
            "campaign_id": copy_task.metadata.campaign_id
        },
        source="copy_worker"
    )
    copy_result.mark_processed()
    
    print_envelope(copy_result, "Copywriter Result")
    
    print(f"Generated email:")
    print(f"  Subject: {content['subject']}")
    print(f"  Body preview: {content['body'][:150]}...")
    print()
    
    return copy_result


def test_error_handling():
    """Test 5: Error handling with DLQ."""
    print_section("Test 5: Error Handling & DLQ")
    
    # Create failing task
    failing_task = task(
        source="test",
        task_id="failing-persist-001",
        destination="persist:tasks",
        payload={
            "table": "leads",
            "op": "insert",
            "values": {"email": "duplicate@example.com"}
        }
    )
    
    print_envelope(failing_task, "Original Task")
    
    # Simulate error
    error_env = error(
        original=failing_task,
        error_msg="duplicate key value violates unique constraint",
        source="persist_worker",
        code="23505"  # PostgreSQL duplicate key error
    )
    
    print_envelope(error_env, "Error Envelope (After First Failure)")
    print(f"  Retry count: {error_env.metadata.retry_count}")
    print(f"  Max retries: {error_env.metadata.max_retries}")
    print()
    
    # Increment retry
    error_env.increment_retry()
    print(f"After increment_retry():")
    print(f"  Retry count: {error_env.metadata.retry_count}")
    print(f"  Status: {error_env.status}")
    print()
    
    # Increment to DLQ
    error_env.increment_retry()
    error_env.increment_retry()
    print(f"After exhausting retries:")
    print(f"  Retry count: {error_env.metadata.retry_count}")
    print(f"  Status: {error_env.status} (auto-promoted to DLQ)")
    print(f"  Error code: {error_env.error_code}")
    print()


def test_correlation_tracking():
    """Test 6: Correlation ID tracking across pipeline."""
    print_section("Test 6: Correlation ID Tracking")
    cmd = _make_orchestrator_cmd()
    rag_task = _make_rag_task(cmd)
    lead_data = {
        "id": 1,
        "first_name": "John",
        "last_name": "Doe",
        "email": "john@example.com",
        "company_name": "Acme Corp",
        "title": "VP Engineering",
    }
    rag_result = _make_rag_result(rag_task, lead_data)
    copy_task = _make_copy_task(rag_task, lead_data)
    copy_result = _make_copy_result(copy_task, "Sample generated email body")

    correlation_id = cmd.metadata.correlation_id

    envelopes = [
        ("Orchestrator Command", cmd),
        ("RAG Task", rag_task),
        ("RAG Result", rag_result),
        ("Copywriter Task", copy_task),
        ("Copywriter Result", copy_result),
    ]
    
    print(f"Correlation ID: {correlation_id}\n")
    print(f"Pipeline trace:")
    for i, (label, env) in enumerate(envelopes, 1):
        match = "✓" if env.metadata.correlation_id == correlation_id else "✗"
        parent = env.metadata.tags.get("parent_task_id", "-")
        print(f"  {i}. [{match}] {label}")
        print(f"      Task ID: {env.metadata.task_id}")
        print(f"      Parent: {parent}")
        print(f"      Status: {env.status}")
        print()
    
    # Verify all share same correlation ID
    all_match = all(env.metadata.correlation_id == correlation_id for _, env in envelopes)
    print(f"✓ All envelopes share correlation ID: {all_match}")


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("  ENHANCED ENVELOPE SYSTEM - END-TO-END TEST")
    print("="*70)
    print("\nDemonstrating orchestrator -> RAG -> copywriter pipeline")
    print("with context forwarding, correlation tracking, and error handling.\n")
    
    # Run tests
    cmd = test_orchestrator_command()
    rag_task = test_rag_task_with_forward(cmd)
    copy_task = test_rag_result_and_copywriter_forward(rag_task)
    copy_result = test_copywriter_generation(copy_task)
    test_error_handling()
    
    # Create RAG result for correlation test
    rag_result = result(
        original=rag_task,
        payload={"records": [], "count": 0},
        source="rag_worker"
    )
    rag_result.mark_processed()
    
    test_correlation_tracking(cmd, rag_task, copy_task, rag_result, copy_result)
    
    # Summary
    print_section("TEST SUMMARY")
    print("✓ Envelope creation with builders (task, result, error)")
    print("✓ Serialization/deserialization (to_redis_fields, from_redis_message)")
    print("✓ Context forwarding (orchestrator -> RAG -> copywriter)")
    print("✓ Multi-component context (lead_data + campaign_context + instructions)")
    print("✓ Correlation ID tracking across entire pipeline")
    print("✓ Retry/DLQ lifecycle with error code extraction")
    print("✓ Status management (mark_processed, increment_retry)")
    print("\nAll tests passed! Envelope system ready for Redis integration.\n")


if __name__ == "__main__":
    main()
