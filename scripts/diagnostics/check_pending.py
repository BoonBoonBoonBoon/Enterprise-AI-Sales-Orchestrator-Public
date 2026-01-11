import redis, os
from dotenv import load_dotenv

load_dotenv()
tenant_id = os.getenv("TENANT_ID", "agentic-dev")
r = redis.from_url(os.getenv('REDIS_URL'), decode_responses=True)

stream = f"{tenant_id}:agents:persistence:tasks"
groups_to_check = ["persistence-workers", "persistence_workers"]

for group in groups_to_check:
    try:
        pending = r.xpending(stream, group)
    except Exception as e:
        print(f"Group '{group}' not available on {stream}: {e}")
        continue
    print(f"\nGroup: {group}\nPending messages: {pending}")

# Check pending details
    if isinstance(pending, dict) and pending.get('pending', 0) > 0:
        details = r.xpending_range(
            stream,
            group,
            min='-',
            max='+',
            count=10
        )
        print(f"Pending details:")
        for msg in details:
            print(f"  {msg}")
