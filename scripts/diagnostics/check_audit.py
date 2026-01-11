"""Quick check of audit events."""
from services.redis import RedisStreamsClient as RedisPubSub
from agent.tools.redis import config as rconf
from agent.utils.typed_envelope import from_redis_message

r = RedisPubSub()
stream = rconf.full_key(rconf.STREAM_AUDIT_EVENTS)
entries = r.client.xrevrange(stream, count=10)

print(f'Audit events in {stream}:')
print(f'Total: {len(entries)}\n')

for msg_id, fields in entries:
    env = from_redis_message(fields)
    payload = env.payload
    print(f'{msg_id}:')
    print(f'  Event: {payload.get("event_type")}')
    print(f'  Command: {payload.get("command_type")}')
    print(f'  Correlation: {payload.get("correlation_id")}')
    print(f'  Target: {payload.get("target_stream", "N/A")}')
    print(f'  Tasks: {payload.get("task_count", "N/A")}')
    print()
