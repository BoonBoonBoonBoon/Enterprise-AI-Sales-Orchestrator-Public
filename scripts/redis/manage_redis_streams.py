#!/usr/bin/env python
"""
Redis Stream Migration and Management Utility

This script helps manage the transition to the new canonical stream naming convention.

Usage:
    # Audit current streams
    python migrate_streams_v2.py --audit
    
    # Visualize data flow
    python migrate_streams_v2.py --visualize
    
    # Initialize all streams
    python migrate_streams_v2.py --initialize
    
    # Migrate legacy streams (DRY RUN)
    python migrate_streams_v2.py --migrate
    
    # Migrate and delete old streams (DANGEROUS!)
    python migrate_streams_v2.py --migrate --delete-old
    
    # Verify consumer groups
    python migrate_streams_v2.py --verify
    
    # Export configuration
    python migrate_streams_v2.py --export config.json
"""

import os
import sys
import redis
import json
from typing import Dict, List
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.redis.stream_registry import get_registry, Tier, StreamType


class StreamManager:
    """Manages Redis streams using the canonical registry"""
    
    def __init__(self, redis_client, tenant_id: str):
        self.redis = redis_client
        self.tenant_id = tenant_id
        self.registry = get_registry()
    
    def audit_streams(self) -> Dict[str, any]:
        """Audit all existing streams and identify issues"""
        print("=" * 80)
        print("  REDIS STREAM AUDIT")
        print("=" * 80)
        print(f"\nTenant: {self.tenant_id}\n")
        
        # Get all streams from Redis
        all_keys = self.redis.keys(f"{self.tenant_id}:*")
        
        # Separate stream keys from other keys
        existing_streams = []
        for key in all_keys:
            try:
                self.redis.xinfo_stream(key)
                existing_streams.append(key)
            except:
                pass
        
        # Get expected streams from registry
        expected_streams = set(self.registry.get_all_streams(self.tenant_id).values())
        
        # Categorize
        canonical = [s for s in existing_streams if s in expected_streams]
        legacy = [s for s in existing_streams if s not in expected_streams and self._is_legacy(s)]
        unknown = [s for s in existing_streams if s not in expected_streams and not self._is_legacy(s)]
        missing = [s for s in expected_streams if s not in existing_streams]
        
        # Print results
        self._print_stream_list("CANONICAL STREAMS", canonical, "✓")
        self._print_stream_list("LEGACY STREAMS", legacy, "⚠", show_migration=True)
        self._print_stream_list("UNKNOWN STREAMS", unknown, "?")
        self._print_stream_list("MISSING STREAMS", missing, "✗", show_length=False)
        
        print("\n" + "=" * 80)
        print(f"SUMMARY: {len(canonical)} canonical, {len(legacy)} legacy, "
              f"{len(unknown)} unknown, {len(missing)} missing")
        print("=" * 80 + "\n")
        
        return {
            "canonical": canonical,
            "legacy": legacy,
            "unknown": unknown,
            "missing": missing
        }
    
    def _print_stream_list(self, title: str, streams: List[str], symbol: str, 
                          show_migration: bool = False, show_length: bool = True):
        """Helper to print stream lists"""
        print(f"\n{title}")
        print("-" * 80)
        if streams:
            for stream in sorted(streams):
                if show_length:
                    try:
                        length = self.redis.xlen(stream)
                        print(f"  {symbol} {stream} ({length} messages)")
                    except:
                        print(f"  {symbol} {stream}")
                else:
                    print(f"  {symbol} {stream}")
                
                if show_migration:
                    suggested = self._suggest_migration_target(stream)
                    if suggested:
                        print(f"     → Migrate to: {suggested}")
        else:
            print("  (none)")
    
    def _is_legacy(self, stream_key: str) -> bool:
        """Check if stream uses legacy naming"""
        legacy_patterns = [
            f"{self.tenant_id}:rag:tasks",
            f"{self.tenant_id}:rag:results",
            f"{self.tenant_id}:persist:tasks",
            f"{self.tenant_id}:persist:results",
            f"{self.tenant_id}:copy:tasks",
            f"{self.tenant_id}:copy:results",
            # Legacy Tier-2 flat naming
            f"{self.tenant_id}:leads:tasks",
            f"{self.tenant_id}:leads:results",
            f"{self.tenant_id}:outreach:tasks",
            f"{self.tenant_id}:outreach:results",
            # Legacy Tier-2 hierarchical name (deprecated orchestrator name)
            f"{self.tenant_id}:orchestrators:outreach:tasks",
            f"{self.tenant_id}:orchestrators:outreach:results",
        ]
        return stream_key in legacy_patterns
    
    def _suggest_migration_target(self, legacy_stream: str) -> str:
        """Suggest the new stream name for a legacy stream"""
        mapping = {
            f"{self.tenant_id}:rag:tasks": f"{self.tenant_id}:agents:rag:tasks",
            f"{self.tenant_id}:rag:results": f"{self.tenant_id}:agents:rag:results",
            f"{self.tenant_id}:persist:tasks": f"{self.tenant_id}:agents:persistence:tasks",
            f"{self.tenant_id}:persist:results": f"{self.tenant_id}:agents:persistence:results",
            f"{self.tenant_id}:copy:tasks": f"{self.tenant_id}:agents:copywriter:tasks",
            f"{self.tenant_id}:copy:results": f"{self.tenant_id}:agents:copywriter:results",
            # Tier-2 flat naming → canonical hierarchical naming
            f"{self.tenant_id}:leads:tasks": f"{self.tenant_id}:orchestrators:leads:tasks",
            f"{self.tenant_id}:leads:results": f"{self.tenant_id}:orchestrators:leads:results",
            f"{self.tenant_id}:outreach:tasks": f"{self.tenant_id}:orchestrators:outbound:tasks",
            f"{self.tenant_id}:outreach:results": f"{self.tenant_id}:orchestrators:outbound:results",
            # Deprecated hierarchical name → canonical hierarchical name
            f"{self.tenant_id}:orchestrators:outreach:tasks": f"{self.tenant_id}:orchestrators:outbound:tasks",
            f"{self.tenant_id}:orchestrators:outreach:results": f"{self.tenant_id}:orchestrators:outbound:results",
        }
        return mapping.get(legacy_stream, None)
    
    def initialize_all_streams(self):
        """Initialize all streams and consumer groups from registry"""
        print("\n" + "=" * 80)
        print("  INITIALIZING STREAMS")
        print("=" * 80)
        
        all_streams = self.registry.get_all_streams(self.tenant_id)
        created = 0
        existed = 0
        errors = 0
        
        for stream_name, stream_key in sorted(all_streams.items()):
            stream_def = self.registry._streams[stream_name]
            
            if stream_def.consumer_group:
                try:
                    self.redis.xgroup_create(
                        stream_key,
                        stream_def.consumer_group,
                        id="0",
                        mkstream=True
                    )
                    print(f"✓ Created {stream_key} (group: {stream_def.consumer_group})")
                    created += 1
                except Exception as e:
                    if "BUSYGROUP" in str(e):
                        print(f"✓ {stream_key} (already exists)")
                        existed += 1
                    else:
                        print(f"✗ Error: {stream_key}: {e}")
                        errors += 1
            else:
                try:
                    msg_id = self.redis.xadd(stream_key, {"_init": "true"})
                    self.redis.xdel(stream_key, msg_id)
                    print(f"✓ Created {stream_key} (no consumer group)")
                    created += 1
                except Exception as e:
                    print(f"✗ Error: {stream_key}: {e}")
                    errors += 1
        
        print(f"\n✓ Created {created}, Already existed {existed}, Errors {errors}")
    
    def migrate_legacy_streams(self, delete_old: bool = False):
        """Migrate all legacy streams to new naming"""
        audit = self.audit_streams()
        
        if not audit['legacy']:
            print("\n✓ No legacy streams to migrate!")
            return
        
        print("\n" + "=" * 80)
        print("  MIGRATING LEGACY STREAMS")
        print("=" * 80)
        
        if delete_old:
            print("\n⚠  WARNING: --delete-old flag set - old streams will be DELETED after migration!")
            print("   Press Ctrl+C within 5 seconds to cancel...")
            import time
            time.sleep(5)
        
        total_migrated = 0
        
        for old_stream in audit['legacy']:
            new_stream = self._suggest_migration_target(old_stream)
            if new_stream:
                count = self._migrate_stream(old_stream, new_stream, delete_old)
                total_migrated += count
            else:
                print(f"⚠ No migration target for: {old_stream}")
        
        print(f"\n✓ Migration complete: {total_migrated} total messages migrated")
    
    def _migrate_stream(self, old_stream: str, new_stream: str, delete_old: bool) -> int:
        """Migrate messages from old stream to new stream"""
        print(f"\nMigrating: {old_stream} → {new_stream}")
        print("-" * 80)
        
        total = 0
        last_id = "-"
        batch_size = 100
        
        while True:
            messages = self.redis.xrange(old_stream, last_id, "+", count=batch_size)
            if not messages:
                break
            
            for msg_id, fields in messages:
                fields['_migrated_from'] = old_stream
                fields['_migration_time'] = datetime.utcnow().isoformat()
                fields['_original_id'] = msg_id
                self.redis.xadd(new_stream, fields)
                total += 1
                last_id = msg_id
            
            print(f"  Migrated batch: {len(messages)} messages (total: {total})")
        
        print(f"✓ Migrated {total} messages")
        
        if delete_old and total > 0:
            new_count = self.redis.xlen(new_stream)
            if new_count >= total:
                self.redis.delete(old_stream)
                print(f"✓ Deleted old stream: {old_stream}")
            else:
                print(f"⚠ NOT deleting - verification failed (expected {total}, found {new_count})")
        
        return total
    
    def verify_consumers(self):
        """Verify all consumer groups are properly configured"""
        print("\n" + "=" * 80)
        print("  VERIFYING CONSUMER GROUPS")
        print("=" * 80)
        
        ok_count = 0
        issue_count = 0
        
        for stream_name, stream_def in self.registry._streams.items():
            if not stream_def.consumer_group:
                continue
            
            stream_key = stream_def.get_key(self.tenant_id)
            
            try:
                self.redis.xinfo_stream(stream_key)
                groups = self.redis.xinfo_groups(stream_key)
                group_names = [g['name'] for g in groups]
                
                if stream_def.consumer_group not in group_names:
                    print(f"⚠ {stream_key}: Missing consumer group '{stream_def.consumer_group}'")
                    issue_count += 1
                else:
                    pending = self.redis.xpending(stream_key, stream_def.consumer_group)
                    if pending and pending[0] > 0:
                        print(f"⚠ {stream_key}: {pending[0]} pending messages")
                        issue_count += 1
                    else:
                        print(f"✓ {stream_key}: {stream_def.consumer_group} OK")
                        ok_count += 1
            
            except redis.exceptions.ResponseError as e:
                if "no such key" in str(e).lower():
                    print(f"✗ {stream_key}: Stream does not exist")
                else:
                    print(f"✗ {stream_key}: {e}")
                issue_count += 1
        
        print(f"\n✓ {ok_count} OK, {issue_count} issues found")
    
    def export_config(self, filepath: str):
        """Export current stream configuration to JSON"""
        config = {
            "tenant_id": self.tenant_id,
            "timestamp": datetime.utcnow().isoformat(),
            "streams": {}
        }
        
        for stream_name, stream_key in self.registry.get_all_streams(self.tenant_id).items():
            stream_def = self.registry._streams[stream_name]
            
            try:
                info = self.redis.xinfo_stream(stream_key)
                length = info["length"]
            except:
                length = 0
            
            config["streams"][stream_key] = {
                "tier": stream_def.tier.value,
                "component": stream_def.component,
                "type": stream_def.stream_type.value,
                "consumer_group": stream_def.consumer_group,
                "max_len": stream_def.max_len,
                "retention_hours": stream_def.retention_hours,
                "current_length": length,
                "description": stream_def.description
            }
        
        with open(filepath, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"\n✓ Exported configuration to: {filepath}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Redis Stream Migration and Management Utility",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("--tenant", default=os.getenv("TENANT_ID", "agentic-dev"),
                       help="Tenant ID (default: from TENANT_ID env var)")
    parser.add_argument("--audit", action="store_true",
                       help="Audit existing streams")
    parser.add_argument("--migrate", action="store_true",
                       help="Migrate legacy streams to new naming")
    parser.add_argument("--delete-old", action="store_true",
                       help="Delete old streams after migration (DANGEROUS!)")
    parser.add_argument("--initialize", action="store_true",
                       help="Initialize all streams and consumer groups")
    parser.add_argument("--verify", action="store_true",
                       help="Verify consumer groups")
    parser.add_argument("--export", type=str, metavar="FILE",
                       help="Export configuration to JSON file")
    parser.add_argument("--visualize", action="store_true",
                       help="Visualize data flow")
    
    args = parser.parse_args()
    
    # Connect to Redis
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        print("Error: REDIS_URL environment variable not set")
        sys.exit(1)
    
    redis_client = redis.from_url(redis_url, decode_responses=True)
    manager = StreamManager(redis_client, args.tenant)
    
    # Execute requested operations
    if args.visualize:
        print(get_registry().visualize_data_flow(args.tenant))
    
    if args.audit:
        manager.audit_streams()
    
    if args.migrate:
        manager.migrate_legacy_streams(delete_old=args.delete_old)
    
    if args.initialize:
        manager.initialize_all_streams()
    
    if args.verify:
        manager.verify_consumers()
    
    if args.export:
        manager.export_config(args.export)
    
    # If no arguments, show help
    if not any([args.audit, args.migrate, args.initialize, args.verify, args.export, args.visualize]):
        parser.print_help()


if __name__ == "__main__":
    main()
