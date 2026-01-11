"""Check namespace configuration."""
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

print('Environment Variables:')
print(f'  REDIS_NAMESPACE from .env: {os.getenv("REDIS_NAMESPACE")}')

# Now import config to see what it uses
from agent.tools.redis import config as rconf

print(f'\nConfig Module:')
print(f'  NAMESPACE being used: {rconf.NAMESPACE}')
print(f'  Full key example: {rconf.full_key("test:stream")}')

# Test connection
from services.redis import RedisStreamsClient as RedisPubSub
r = RedisPubSub()

# List keys
keys = r.client.keys(f'{rconf.NAMESPACE}:*')
print(f'\nRedis Keys with "{rconf.NAMESPACE}" namespace: {len(keys)}')
for key in keys[:5]:
    key_str = key.decode() if isinstance(key, bytes) else key
    print(f'  - {key_str}')

# Also check for agentic-dev keys
dev_keys = r.client.keys('agentic-dev:*')
print(f'\nRedis Keys with "agentic-dev" namespace: {len(dev_keys)}')
for key in dev_keys[:5]:
    key_str = key.decode() if isinstance(key, bytes) else key
    print(f'  - {key_str}')
