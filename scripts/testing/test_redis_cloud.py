"""Test Redis Cloud connection and enqueue orchestrator command."""
from dotenv import load_dotenv
load_dotenv()  # Load .env file first!

from services.redis import RedisStreamsClient as RedisPubSub
from agent.tools.redis import config as rconf
from agent.utils.typed_envelope import task, to_redis_fields
import time

print('='*80)
print('REDIS CLOUD CONNECTION TEST')
print('='*80)

r = RedisPubSub()
print('✅ Connected to Redis Cloud')
print(f'Namespace: {rconf.NAMESPACE}')

# Check database info
info = r.client.info('server')
print(f"Redis version: {info.get('redis_version', 'N/A')}")

# List current keys
keys = r.client.keys(rconf.full_key('*'))
print(f'\nTotal keys with namespace "{rconf.NAMESPACE}": {len(keys)}')
if keys:
    print(f'\nSample keys (first 10):')
    for key in keys[:10]:
        key_str = key.decode() if isinstance(key, bytes) else key
        print(f'  - {key_str}')
else:
    print('  (no keys found)')

print('\n' + '='*80)
print('ENQUEUING TEST COMMAND TO ORCHESTRATOR')
print('='*80)

# Enqueue a query_leads command
cmd_envelope = task(
    source="test_script",
    task_id=f"cloud-test-{int(time.time())}",
    destination="orchestrator:commands",
    payload={
        "type": "query_leads",
        "query": {
            "table": "leads",
            "filters": {"email": "cloudtest@example.com"},
            "limit": 5
        }
    },
    campaign_id="redis_cloud_test"
)

correlation_id = cmd_envelope.metadata.correlation_id

msg_id = r.client.xadd(
    rconf.full_key("orchestrator:commands"),
    to_redis_fields(cmd_envelope),
    maxlen=rconf.STREAM_MAXLEN,
)

print(f'✅ Command enqueued to orchestrator:commands')
print(f'   Message ID: {msg_id}')
print(f'   Correlation ID: {correlation_id}')
print(f'   Stream: {rconf.full_key("orchestrator:commands")}')

# Check stream length
stream_len = r.client.xlen(rconf.full_key("orchestrator:commands"))
print(f'   Stream length: {stream_len}')

print('\n' + '='*80)
print('VERIFICATION')
print('='*80)

# List recent entries
entries = r.client.xrevrange(rconf.full_key("orchestrator:commands"), count=3)
print(f'\nLast 3 commands in orchestrator:commands:')
for msg_id, fields in entries:
    from agent.utils.typed_envelope import from_redis_message
    env = from_redis_message(fields)
    print(f'  {msg_id}: type={env.payload.get("type")}, corr={env.metadata.correlation_id[:12]}...')

print('\n✅ Test complete! Check Redis Cloud UI to verify the orchestrator:commands stream.')
