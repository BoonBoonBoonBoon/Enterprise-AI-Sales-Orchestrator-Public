import redis

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

# Get all keys that look like stream names
all_keys = r.keys('*:*:*:*')

print(f'Found {len(all_keys)} potential streams:\n')

for key in sorted(all_keys):
    count = r.xlen(key)
    if count > 0:
        print(f'  {key}: {count} messages')

print(f'\nTotal non-empty streams: {sum(1 for k in all_keys if r.xlen(k) > 0)}')

# Also check for any "rag" related streams
rag_streams = r.keys('*rag*')
print(f'\nAll RAG-related streams:')
for stream in rag_streams:
    count = r.xlen(stream)
    print(f'  {stream}: {count} messages')
