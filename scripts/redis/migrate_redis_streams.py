#!/usr/bin/env python3
"""
Redis Stream Naming Migration Script

Migrates from legacy/flat naming to the canonical hierarchical naming:
    agentic-dev:leads:tasks → agentic-dev:orchestrators:leads:tasks
    agentic-dev:outreach:tasks → agentic-dev:orchestrators:outbound:tasks
    agentic-dev:orchestrators:outreach:tasks → agentic-dev:orchestrators:outbound:tasks
    etc.
"""

import redis
import os
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

REDIS_URL = os.getenv('REDIS_URL')
TENANT = 'agentic-dev'

# Mapping of old naming to new naming
MIGRATIONS = {
    f'{TENANT}:leads:tasks': f'{TENANT}:orchestrators:leads:tasks',
    f'{TENANT}:leads:results': f'{TENANT}:orchestrators:leads:results',
    f'{TENANT}:outreach:tasks': f'{TENANT}:orchestrators:outbound:tasks',
    f'{TENANT}:outreach:results': f'{TENANT}:orchestrators:outbound:results',
    f'{TENANT}:orchestrators:outreach:tasks': f'{TENANT}:orchestrators:outbound:tasks',
    f'{TENANT}:orchestrators:outreach:results': f'{TENANT}:orchestrators:outbound:results',
    f'{TENANT}:rag:tasks': f'{TENANT}:agents:rag:tasks',
    f'{TENANT}:rag:results': f'{TENANT}:agents:rag:results',
    f'{TENANT}:copy:tasks': f'{TENANT}:agents:copywriter:tasks',
    f'{TENANT}:copy:results': f'{TENANT}:agents:copywriter:results',
    f'{TENANT}:persist:tasks': f'{TENANT}:agents:persistence:tasks',
    f'{TENANT}:persist:results': f'{TENANT}:agents:persistence:results',
}

def migrate_stream(r: redis.Redis, old_name: str, new_name: str) -> int:
    """Migrate all messages from old stream to new stream."""
    
    # Check if old stream exists
    if not r.exists(old_name):
        logger.info(f"Stream {old_name} does not exist, skipping")
        return 0
    
    # Get message count
    old_count = r.xlen(old_name)
    if old_count == 0:
        logger.info(f"Stream {old_name} is empty")
        return 0
    
    logger.info(f"Migrating {old_count} messages from {old_name} → {new_name}")
    
    # Read all messages from old stream
    messages_migrated = 0
    last_id = '0'
    
    while True:
        # Read batch of messages using correct API
        messages = r.xrange(old_name, min=f'({last_id}', count=100)
        if not messages:
            break
        
        # Add each message to new stream with same ID
        for msg_id, msg_data in messages:
            try:
                r.xadd(new_name, msg_data, id=msg_id)
                messages_migrated += 1
                last_id = msg_id
            except Exception as e:
                logger.error(f"Failed to migrate message {msg_id}: {e}")
                return -1
    
    logger.info(f"✓ Successfully migrated {messages_migrated} messages")
    
    # Delete old stream after migration
    logger.info(f"Deleting old stream {old_name}")
    r.delete(old_name)
    
    return messages_migrated

def main():
    if not REDIS_URL:
        logger.error("REDIS_URL environment variable not set")
        return False
    
    try:
        r = redis.from_url(REDIS_URL, decode_responses=True)
        r.ping()
        logger.info("✓ Connected to Redis Cloud")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        return False
    
    # Show current state
    logger.info(f"\nCurrent streams in {TENANT}:")
    all_streams = sorted([k for k in r.keys(f'{TENANT}:*') if ':tasks' in k or ':results' in k])
    for stream in all_streams:
        length = r.xlen(stream)
        logger.info(f"  {stream}: {length} messages")
    
    logger.info(f"\n{'='*70}")
    logger.info("Starting migration...")
    logger.info(f"{'='*70}\n")
    
    total_migrated = 0
    failed = 0
    
    # Perform migrations
    for old_name, new_name in MIGRATIONS.items():
        try:
            count = migrate_stream(r, old_name, new_name)
            if count >= 0:
                total_migrated += count
            else:
                failed += 1
        except Exception as e:
            logger.error(f"Migration error for {old_name}: {e}")
            failed += 1
    
    logger.info(f"\n{'='*70}")
    logger.info(f"Migration complete!")
    logger.info(f"  Total messages migrated: {total_migrated}")
    logger.info(f"  Failed migrations: {failed}")
    logger.info(f"{'='*70}\n")
    
    # Show new state
    logger.info(f"New streams in {TENANT}:")
    new_streams = sorted([k for k in r.keys(f'{TENANT}:*') if ':tasks' in k or ':results' in k])
    for stream in new_streams:
        length = r.xlen(stream)
        logger.info(f"  {stream}: {length} messages")
    
    return failed == 0

if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
