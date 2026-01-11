import redis, os
from dotenv import load_dotenv

load_dotenv()
tenant_id = os.getenv("TENANT_ID", "agentic-dev")
r = redis.from_url(os.getenv('REDIS_URL'), decode_responses=True)

stream = f"{tenant_id}:agents:persistence:tasks"
groups_to_check = ["persistence-workers", "persistence_workers"]

for group in groups_to_check:
    try:
        consumers = r.xinfo_consumers(stream, group)
    except Exception as e:
        print(f"Group '{group}' not available on {stream}: {e}")
        continue

    print(f"\nGroup: {group}")
    print(f"Active consumers: {len(consumers)}\n")
    for c in consumers[:10]:
        print(f"  {c['name']}: pending={c['pending']}, idle={c['idle']}ms")
