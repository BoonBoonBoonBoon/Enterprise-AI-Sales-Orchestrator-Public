"""Demo script for new orchestrator routing capabilities.

Tests:
- query_leads command (direct RAG routing)
- generate_copy command (direct copywriter routing)
- Audit event emission
- Optional workflow state tracking
"""
import argparse
import time
from typing import Optional

from services.redis import RedisStreamsClient as RedisPubSub
from agent.tools.redis import config as rconf
from agent.utils.typed_envelope import task, to_redis_fields, Priority


def enqueue_query_leads_command(
    table: str = "leads",
    filters: Optional[dict] = None,
    limit: int = 10,
    campaign_id: Optional[str] = None,
    wait: bool = False
) -> str:
    """Enqueue a query_leads command to orchestrator."""
    r = RedisPubSub()
    
    query_spec = {
        "table": table,
        "filters": filters or {},
        "limit": limit,
        "order_by": "created_at",
        "descending": True
    }
    
    cmd_envelope = task(
        source="demo_script",
        task_id=f"cmd-query-{int(time.time())}",
        destination="orchestrator:commands",
        payload={
            "type": "query_leads",
            "query": query_spec
        },
        campaign_id=campaign_id,
        priority=Priority.NORMAL
    )
    
    correlation_id = cmd_envelope.metadata.correlation_id
    
    msg_id = r.client.xadd(
        rconf.full_key("orchestrator:commands"),
        to_redis_fields(cmd_envelope),
        maxlen=rconf.STREAM_MAXLEN,
    )
    
    print(f"✅ Enqueued query_leads command")
    print(f"   Message ID: {msg_id}")
    print(f"   Correlation ID: {correlation_id}")
    print(f"   Query: {query_spec}")
    
    if wait:
        print(f"\n⏳ Waiting for result on {rconf.STREAM_RESULTS}...")
        _wait_for_result(r, correlation_id, timeout=30)
    
    return correlation_id


def enqueue_generate_copy_command(
    lead_data: dict,
    campaign_context: Optional[dict] = None,
    instructions: Optional[dict] = None,
    campaign_id: Optional[str] = None,
    wait: bool = False
) -> str:
    """Enqueue a generate_copy command to orchestrator."""
    r = RedisPubSub()
    
    cmd_envelope = task(
        source="demo_script",
        task_id=f"cmd-copy-{int(time.time())}",
        destination="orchestrator:commands",
        payload={
            "type": "generate_copy",
            "lead_data": lead_data,
            "campaign_context": campaign_context or {},
            "instructions": instructions or {}
        },
        campaign_id=campaign_id,
        priority=Priority.HIGH
    )
    
    correlation_id = cmd_envelope.metadata.correlation_id
    
    msg_id = r.client.xadd(
        rconf.full_key("orchestrator:commands"),
        to_redis_fields(cmd_envelope),
        maxlen=rconf.STREAM_MAXLEN,
    )
    
    print(f"✅ Enqueued generate_copy command")
    print(f"   Message ID: {msg_id}")
    print(f"   Correlation ID: {correlation_id}")
    print(f"   Lead: {lead_data.get('email', 'N/A')}")
    
    if wait:
        print(f"\n⏳ Waiting for result on {rconf.STREAM_RESULTS_COPY}...")
        _wait_for_copy_result(r, correlation_id, timeout=30)
    
    return correlation_id


def _wait_for_result(r: RedisPubSub, correlation_id: str, timeout: int = 30):
    """Wait for RAG result matching correlation_id."""
    results_stream = rconf.full_key(rconf.STREAM_RESULTS)
    start = time.time()
    
    while time.time() - start < timeout:
        entries = r.client.xrevrange(results_stream, count=50)
        for msg_id, fields in entries:
            from agent.utils.typed_envelope import from_redis_message
            envelope = from_redis_message(fields)
            if envelope.metadata.correlation_id == correlation_id:
                print(f"\n✅ Found result!")
                print(f"   Task ID: {envelope.metadata.task_id}")
                print(f"   Status: {envelope.status}")
                if envelope.payload.get("count"):
                    print(f"   Record count: {envelope.payload['count']}")
                return
        
        time.sleep(1)
    
    print(f"\n⏱️  Timeout after {timeout}s - no result found")


def _wait_for_copy_result(r: RedisPubSub, correlation_id: str, timeout: int = 30):
    """Wait for copywriter result matching correlation_id."""
    results_stream = rconf.full_key(rconf.STREAM_RESULTS_COPY)
    start = time.time()
    
    while time.time() - start < timeout:
        entries = r.client.xrevrange(results_stream, count=50)
        for msg_id, fields in entries:
            from agent.utils.typed_envelope import from_redis_message
            envelope = from_redis_message(fields)
            if envelope.metadata.correlation_id == correlation_id:
                print(f"\n✅ Found copy result!")
                print(f"   Task ID: {envelope.metadata.task_id}")
                print(f"   Status: {envelope.status}")
                if envelope.payload.get("subject"):
                    print(f"   Subject: {envelope.payload['subject']}")
                return
        
        time.sleep(1)
    
    print(f"\n⏱️  Timeout after {timeout}s - no result found")


def check_audit_events(correlation_id: str, count: int = 10):
    """Check audit events for a correlation ID."""
    r = RedisPubSub()
    audit_stream = rconf.full_key(rconf.STREAM_AUDIT_EVENTS)
    
    print(f"\n🔍 Checking audit events for correlation_id: {correlation_id}")
    
    try:
        entries = r.client.xrevrange(audit_stream, count=count)
        found = False
        
        for msg_id, fields in entries:
            from agent.utils.typed_envelope import from_redis_message
            envelope = from_redis_message(fields)
            
            if envelope.metadata.correlation_id == correlation_id:
                found = True
                print(f"\n   Event: {envelope.payload.get('event_type')}")
                print(f"   Command: {envelope.payload.get('command_type')}")
                print(f"   Target: {envelope.payload.get('target_stream', 'N/A')}")
                print(f"   Tasks: {envelope.payload.get('task_count', 'N/A')}")
                print(f"   Time: {envelope.payload.get('timestamp')}")
        
        if not found:
            print("   No audit events found (yet)")
    
    except Exception as e:
        print(f"   Error reading audit stream: {e}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Demo orchestrator routing")
    parser.add_argument(
        "--query",
        action="store_true",
        help="Test query_leads command (RAG routing)"
    )
    parser.add_argument(
        "--copy",
        action="store_true",
        help="Test generate_copy command (copywriter routing)"
    )
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Wait for results"
    )
    parser.add_argument(
        "--check-audit",
        action="store_true",
        help="Check audit events after enqueuing"
    )
    
    args = parser.parse_args()
    
    if args.query:
        correlation_id = enqueue_query_leads_command(
            table="leads",
            filters={"email": "test@example.com"},
            limit=5,
            campaign_id="demo_campaign",
            wait=args.wait
        )
        
        if args.check_audit:
            time.sleep(2)  # Give orchestrator time to process
            check_audit_events(correlation_id)
    
    elif args.copy:
        lead_data = {
            "id": "lead_demo_123",
            "email": "prospect@company.com",
            "first_name": "Alice",
            "company_name": "DemoCorp"
        }
        
        campaign_context = {
            "campaign_name": "Q4 Demo Campaign",
            "step": 1,
            "sender_name": "Sales Team"
        }
        
        instructions = {
            "tone": "professional",
            "language": "en-US",
            "max_length": 200
        }
        
        correlation_id = enqueue_generate_copy_command(
            lead_data=lead_data,
            campaign_context=campaign_context,
            instructions=instructions,
            campaign_id="demo_campaign",
            wait=args.wait
        )
        
        if args.check_audit:
            time.sleep(2)
            check_audit_events(correlation_id)
    
    else:
        parser.print_help()
        return 1
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
