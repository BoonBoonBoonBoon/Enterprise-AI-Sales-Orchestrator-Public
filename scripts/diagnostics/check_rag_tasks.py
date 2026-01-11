"""Check RAG tasks in Redis Cloud."""
from services.redis import RedisStreamsClient as RedisPubSub
from agent.tools.redis import config as rconf
from agent.utils.typed_envelope import from_redis_message

r = RedisPubSub()
stream = rconf.full_key(rconf.STREAM_TASKS)
entries = r.client.xrevrange(stream, count=5)

print(f'Latest tasks in {stream}:')
print(f'Total: {len(entries)}\n')

for msg_id, fields in entries:
    env = from_redis_message(fields)
    query = env.payload.get("query", {})
    print(f'{msg_id}:')
    print(f'  Task ID: {env.metadata.task_id}')
    print(f'  Correlation: {env.metadata.correlation_id}')
    print(f'  Table: {query.get("table", "N/A")}')
    print(f'  Filters: {query.get("filters", {})}')
    print(f'  Source: {env.metadata.source}')
    print()
