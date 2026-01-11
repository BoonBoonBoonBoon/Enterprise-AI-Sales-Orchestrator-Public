#!/usr/bin/env python3
"""
Reset Consumer Groups

Deletes all consumer groups to clear pending messages.
Consumers will recreate them on startup and read from latest messages.
"""

import redis
import os

REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
TENANT_ID = os.getenv('TENANT_ID', 'agentic-dev')

def reset_consumer_groups():
    """Delete all consumer groups"""
    r = redis.Redis.from_url(REDIS_URL)
    
    groups = [
        ('manager:tasks', 'manager-workers'),
        ('orchestrators:leads:tasks', 'leads-workers'),
        ('orchestrators:outbound:tasks', 'outbound-workers'),
    ]
    
    print("🔄 Resetting consumer groups...")
    
    for stream_suffix, group_name in groups:
        stream = f"{TENANT_ID}:{stream_suffix}"
        try:
            r.xgroup_destroy(stream, group_name)
            print(f"  ✅ Deleted {group_name} from {stream}")
        except redis.ResponseError as e:
            if "NOGROUP" in str(e):
                print(f"  ⚠️  {group_name} on {stream} doesn't exist")
            else:
                print(f"  ❌ Error deleting {group_name}: {e}")
    
    print("\n✅ Consumer groups reset!")
    print("   Restart all consumers now - they will recreate groups and read new messages.")

if __name__ == "__main__":
    reset_consumer_groups()
