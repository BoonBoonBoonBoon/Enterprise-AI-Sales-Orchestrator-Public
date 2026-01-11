"""Test workflow state tracking with WORKFLOW_STATE_ENABLED=1."""
import os
os.environ["WORKFLOW_STATE_ENABLED"] = "1"

from agent.orchestrators.workflow_manager import WorkflowManager
from agent.utils.typed_envelope import from_redis_message, task, to_redis_fields
from agent.tools.redis import config as rconf

print(f'Workflow state tracking enabled: {rconf.WORKFLOW_STATE_ENABLED}')
print(f'Workflow state TTL: {rconf.WORKFLOW_STATE_TTL}s\n')

# Create orchestrator
wm = WorkflowManager()
print(f'Orchestrator state tracking: {wm.state_tracking_enabled}\n')

# Enqueue a test command
print('Enqueuing test query_leads command...')
cmd_envelope = task(
    source="test_script",
    task_id=f"test-workflow-state",
    destination="orchestrator:commands",
    payload={
        "type": "query_leads",
        "query": {
            "table": "leads",
            "filters": {"email": "workflow-test@example.com"},
            "limit": 1
        }
    },
    campaign_id="workflow_test_campaign"
)

correlation_id = cmd_envelope.metadata.correlation_id
print(f'Correlation ID: {correlation_id}\n')

wm.r.client.xadd(
    rconf.full_key("orchestrator:commands"),
    to_redis_fields(cmd_envelope),
    maxlen=rconf.STREAM_MAXLEN,
)

# Process the command
print('Processing command...')
entries = wm.r.client.xreadgroup(wm.group, wm.worker_id, {wm.stream: '>'}, count=1, block=1000)

if entries:
    for stream_name, msgs in entries:
        for msg_id, fields in msgs:
            env = from_redis_message(fields)
            cmd_type = env.payload.get("type")
            
            if cmd_type == "query_leads":
                wm._emit_audit_event("command_accepted", env, details={"msg_id": msg_id})
                wm._handle_query_leads(env)
                wm.r.client.xack(wm.stream, wm.group, msg_id)
                print(f'✅ Processed {cmd_type} command\n')

# Check workflow state
print('Checking workflow state...')
state_key = rconf.full_key(rconf.workflow_state_key(correlation_id))
state = wm.r.client.hgetall(state_key)

if state:
    print(f'Workflow state found at {state_key}:')
    for k, v in state.items():
        k_str = k.decode() if isinstance(k, bytes) else k
        v_str = v.decode() if isinstance(v, bytes) else v
        print(f'  {k_str}: {v_str}')
    
    ttl = wm.r.client.ttl(state_key)
    print(f'\nTTL: {ttl}s')
else:
    print('❌ No workflow state found')

# Check audit events
print('\nChecking audit events...')
audit_stream = rconf.full_key(rconf.STREAM_AUDIT_EVENTS)
audit_entries = wm.r.client.xrevrange(audit_stream, count=5)

print(f'Latest {len(audit_entries)} audit events:')
for msg_id, fields in audit_entries:
    env = from_redis_message(fields)
    if env.metadata.correlation_id == correlation_id:
        print(f'  {env.payload.get("event_type")}: {env.payload.get("command_type")} → {env.payload.get("target_stream", "N/A")}')
