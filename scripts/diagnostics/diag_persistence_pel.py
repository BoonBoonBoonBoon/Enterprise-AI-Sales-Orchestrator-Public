"""Quick diagnostic: check persistence stream PEL and consumer groups."""
import os
import redis
from dotenv import load_dotenv

load_dotenv()

r = redis.from_url(os.getenv("REDIS_URL"), decode_responses=True)
tenant = os.getenv("TENANT_ID", "agentic-dev")

streams = [
    f"{tenant}:agents:persistence:tasks",
    f"{tenant}:agents:persistence:results",
]

for stream in streams:
    print(f"\n=== {stream} ===")
    try:
        length = r.xlen(stream)
        print(f"  Length: {length}")
    except Exception as e:
        print(f"  Error getting length: {e}")
        continue

    # Get consumer groups
    try:
        groups = r.xinfo_groups(stream)
        if not groups:
            print("  No consumer groups")
        for g in groups:
            print(f"  Group: {g['name']}")
            print(f"    Consumers: {g['consumers']}")
            print(f"    Pending: {g['pending']}")
            print(f"    Last delivered: {g.get('last-delivered-id', 'N/A')}")

            # Check pending details
            if g["pending"] > 0:
                pending = r.xpending_range(stream, g["name"], min="-", max="+", count=10)
                print(f"    Pending messages (first 10):")
                for p in pending:
                    print(f"      {p}")
    except Exception as e:
        print(f"  Error getting groups: {e}")
