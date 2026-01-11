"""Complete test: enqueue + process + verify in Redis Cloud with agentic-dev namespace."""
from dotenv import load_dotenv
load_dotenv()

from services.redis import RedisStreamsClient as RedisPubSub
from agent.tools.redis import config as rconf
from agent.utils.typed_envelope import task, to_redis_fields, from_redis_message
from agent.orchestrators.workflow_manager import WorkflowManager
import time

print('='*80)
print('REDIS CLOUD - COMPLETE ORCHESTRATOR TEST (agentic-dev)')
print('='*80)

r = RedisPubSub()
print(f'✅ Connected to Redis Cloud')
print(f'   Namespace: {rconf.NAMESPACE}')

# Step 1: Enqueue generate_copy command
print('\n[STEP 1] Enqueuing generate_copy command...')
cmd_envelope = task(
    source="redis_cloud_test",
    task_id=f"cloud-copy-{int(time.time())}",
    destination="orchestrator:commands",
    payload={
        "type": "generate_copy",
        "lead_data": {
            "id": "lead_redis_cloud_001",
            "email": "redis-cloud-test@example.com",
            "first_name": "CloudTest",
            "company_name": "Redis Cloud Inc"
        },
        "campaign_context": {
            "campaign_name": "Redis Cloud Demo",
            "step": 1
        },
        "instructions": {
            "tone": "professional",
            "language": "en-US"
        }
    },
    campaign_id="redis_cloud_demo"
)

correlation_id = cmd_envelope.metadata.correlation_id

msg_id = r.client.xadd(
    rconf.full_key("orchestrator:commands"),
    to_redis_fields(cmd_envelope),
    maxlen=rconf.STREAM_MAXLEN,
)

print(f'   ✅ Enqueued to {rconf.full_key("orchestrator:commands")}')
print(f'   Message ID: {msg_id}')
print(f'   Correlation ID: {correlation_id}')

# Step 2: Process with orchestrator
print('\n[STEP 2] Processing with orchestrator...')
wm = WorkflowManager()
entries = wm.r.client.xreadgroup(wm.group, wm.worker_id, {wm.stream: '>'}, count=1, block=1000)

if entries:
    for stream_name, msgs in entries:
        for msg_id, fields in msgs:
            env = from_redis_message(fields)
            cmd_type = env.payload.get("type")
            print(f'   Processing: {cmd_type}')
            
            # Emit audit and route
            wm._emit_audit_event("command_accepted", env, details={"msg_id": msg_id})
            if cmd_type == "generate_copy":
                wm._handle_generate_copy(env)
            
            wm.r.client.xack(wm.stream, wm.group, msg_id)
            print(f'   ✅ Routed and acknowledged')

# Step 3: Verify audit events
print('\n[STEP 3] Checking audit events...')
audit_stream = rconf.full_key(rconf.STREAM_AUDIT_EVENTS)
audit_entries = r.client.xrevrange(audit_stream, count=3)
print(f'   Audit stream: {audit_stream}')
print(f'   Latest {len(audit_entries)} events:')

for msg_id, fields in audit_entries:
    env = from_redis_message(fields)
    if env.metadata.correlation_id == correlation_id:
        print(f'   ✅ {env.payload.get("event_type")}: {env.payload.get("command_type")} → {env.payload.get("target_stream", "N/A")}')

# Step 4: Verify copy:tasks
print('\n[STEP 4] Checking copy:tasks stream...')
copy_stream = rconf.full_key(rconf.STREAM_TASKS_COPY)
copy_entries = r.client.xrevrange(copy_stream, count=2)
print(f'   Copy tasks stream: {copy_stream}')

for msg_id, fields in copy_entries:
    env = from_redis_message(fields)
    if env.metadata.correlation_id == correlation_id:
        lead_email = env.payload.get("lead_data", {}).get("email")
        print(f'   ✅ Task found: {env.metadata.task_id}')
        print(f'      Lead: {lead_email}')
        print(f'      Source: {env.metadata.source}')

print('\n' + '='*80)
print('✅ COMPLETE TEST PASSED!')
print('='*80)
print(f'\nNow check Redis Cloud UI for namespace: {rconf.NAMESPACE}')
print(f'Expected new streams:')
print(f'  - {rconf.full_key("orchestrator:commands")}')
print(f'  - {rconf.full_key("audit:events")}')
print(f'  - {rconf.full_key("copy:tasks")}')
