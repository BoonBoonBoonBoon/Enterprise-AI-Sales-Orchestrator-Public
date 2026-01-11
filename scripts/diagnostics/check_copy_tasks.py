"""Check copywriter tasks."""
from services.redis import RedisStreamsClient as RedisPubSub
from agent.tools.redis import config as rconf
from agent.utils.typed_envelope import from_redis_message

r = RedisPubSub()
stream = rconf.full_key(rconf.STREAM_TASKS_COPY)
entries = r.client.xrevrange(stream, count=3)

print(f'Latest tasks in {stream}:')
print(f'Total: {len(entries)}\n')

for msg_id, fields in entries:
    env = from_redis_message(fields)
    lead_data = env.payload.get("lead_data", {})
    print(f'{msg_id}:')
    print(f'  Task ID: {env.metadata.task_id}')
    print(f'  Correlation: {env.metadata.correlation_id}')
    print(f'  Lead: {lead_data.get("email", "N/A")}')
    print(f'  Source: {env.metadata.source}')
    print()
