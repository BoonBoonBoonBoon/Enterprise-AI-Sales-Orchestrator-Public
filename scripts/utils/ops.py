#!/usr/bin/env python3
"""Ops CLI - Unified operations tool for Redis Streams

Common operations:
  - Health checks
  - DLQ management
  - Consumer group operations
  - Stream inspection
  - Worker scaling helpers

Usage:
    # Health check
    python scripts/ops.py health --all

    # Inspect stream
    python scripts/ops.py inspect rag:tasks

    # View DLQ
    python scripts/ops.py dlq list

    # Replay DLQ with auto-fix
    python scripts/ops.py dlq replay persist:dlq --auto-fix --limit 20

    # Reset consumer group
    python scripts/ops.py group reset rag:tasks rag-workers

    # Claim stuck messages
    python scripts/ops.py group claim rag:tasks rag-workers --idle-ms 300000

    # Show worker scaling info
    python scripts/ops.py scale info
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add repo root to path
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))

from dotenv import load_dotenv
load_dotenv()

from services.redis import RedisStreamsClient as RedisPubSub
from agent.tools.redis import config as rconf


class OpsCLI:
    """Unified operations CLI for Redis Streams."""
    
    def __init__(self):
        self.redis = RedisPubSub()
    
    def health(self, args):
        """Run health checks."""
        cmd = ["python", "scripts/health_check.py"]
        
        if args.pretty:
            cmd.append("--pretty")
        if args.all:
            cmd.extend(["--max-pending", "1000", "--max-dlq", "100"])
        
        subprocess.run(cmd)
    
    def inspect(self, args):
        """Inspect stream contents."""
        stream = args.stream
        full_key = rconf.full_key(stream)
        
        print(f"\n=== Stream: {full_key} ===")
        
        try:
            # Stream info
            info = self.redis.client.xinfo_stream(full_key)
            print(f"Length: {info.get('length')}")
            print(f"Last ID: {info.get('last-generated-id')}")
            print(f"First entry: {info.get('first-entry')}")
            print(f"Last entry: {info.get('last-entry')}")
            
            # Consumer groups
            try:
                groups = self.redis.client.xinfo_groups(full_key)
                if groups:
                    print(f"\nConsumer Groups: {len(groups)}")
                    for g in groups:
                        print(f"  - {g.get('name')}: {g.get('consumers')} consumers, {g.get('pending')} pending")
            except Exception:
                print("\nNo consumer groups")
            
            # Recent messages
            if args.count > 0:
                print(f"\nRecent {args.count} messages:")
                messages = self.redis.client.xrevrange(full_key, count=args.count)
                for msg_id, fields in messages:
                    print(f"\n  ID: {msg_id}")
                    if args.verbose:
                        for k, v in fields.items():
                            print(f"    {k}: {v[:100] if isinstance(v, str) and len(v) > 100 else v}")
                    else:
                        print(f"    Fields: {list(fields.keys())}")
        
        except Exception as e:
            print(f"Error: {e}")
    
    def dlq_list(self, args):
        """List DLQ streams and their counts."""
        dlqs = [
            ("rag:dlq", "RAG DLQ"),
            ("persist:dlq", "Persistence DLQ"),
            ("copy:dlq", "Copywriter DLQ"),
        ]
        
        print("\n=== DLQ Summary ===")
        for stream, label in dlqs:
            full_key = rconf.full_key(stream)
            try:
                info = self.redis.client.xinfo_stream(full_key)
                length = info.get('length', 0)
                status = "🔴" if length > 100 else "🟡" if length > 10 else "🟢"
                print(f"{status} {label:20} {full_key:40} {length:>5} messages")
                
                if args.verbose and length > 0:
                    # Show recent error
                    messages = self.redis.client.xrange(full_key, count=1)
                    if messages:
                        msg_id, fields = messages[0]
                        error = fields.get('error', {})
                        if isinstance(error, str):
                            try:
                                error = json.loads(error)
                            except:
                                pass
                        error_msg = error.get('message', 'unknown') if isinstance(error, dict) else str(error)
                        print(f"    Latest error: {error_msg[:80]}...")
            except Exception:
                print(f"⚪ {label:20} {full_key:40} (not found)")
        print()
    
    def dlq_replay(self, args):
        """Replay DLQ messages."""
        cmd = ["python", "scripts/dlq_automation.py", "--dlq", args.dlq, "--limit", str(args.limit)]
        
        if args.dry_run:
            cmd.append("--dry-run")
        if args.auto_fix:
            cmd.append("--auto-fix-duplicates")
        if args.transient_only:
            cmd.append("--transient-only")
        
        subprocess.run(cmd)
    
    def group_reset(self, args):
        """Reset consumer group to beginning or specific ID."""
        stream = rconf.full_key(args.stream)
        group = args.group
        msg_id = args.id or "$"
        
        confirm = input(f"Reset group '{group}' on stream '{stream}' to ID '{msg_id}'? (yes/no): ")
        if confirm.lower() != "yes":
            print("Aborted")
            return
        
        try:
            self.redis.client.xgroup_setid(stream, group, msg_id)
            print(f"✓ Reset group '{group}' to ID '{msg_id}'")
        except Exception as e:
            print(f"Error: {e}")
    
    def group_claim(self, args):
        """Claim stuck messages from idle consumers."""
        stream = rconf.full_key(args.stream)
        group = args.group
        idle_ms = args.idle_ms
        
        try:
            # Get pending messages
            pending = self.redis.client.xpending_range(stream, group, "-", "+", count=args.count)
            
            if not pending:
                print("No pending messages")
                return
            
            print(f"Found {len(pending)} pending messages")
            
            claimed = 0
            for entry in pending:
                msg_id = entry["message_id"]
                consumer = entry.get("consumer")
                idle = entry.get("time_since_delivered", 0)
                
                if idle < idle_ms:
                    continue
                
                # Claim message for this worker
                try:
                    self.redis.client.xclaim(
                        stream,
                        group,
                        args.new_consumer,
                        idle_ms,
                        [msg_id]
                    )
                    print(f"✓ Claimed {msg_id} from {consumer} (idle: {idle}ms)")
                    claimed += 1
                except Exception as e:
                    print(f"✗ Failed to claim {msg_id}: {e}")
            
            print(f"\nClaimed {claimed}/{len(pending)} messages")
        
        except Exception as e:
            print(f"Error: {e}")
    
    def scale_info(self, args):
        """Show worker scaling information."""
        print("\n=== Worker Scaling Info ===\n")
        
        # Count active workers by heartbeats
        services = ["rag", "persist", "copy", "orchestrator"]
        for service in services:
            pattern = rconf.full_key(f"ops:hb:{service}:*")
            count = sum(1 for _ in self.redis.client.scan_iter(match=pattern, count=10))
            print(f"{service:15} {count} active workers")
        
        print("\n=== Recommended Actions ===\n")
        
        # Check pending counts and recommend scaling
        streams = [
            ("rag:tasks", "rag-workers", "rag"),
            ("persist:tasks", "persist-writers", "persist"),
            ("copy:tasks", "copy-writers", "copy"),
        ]
        
        for stream, group, service in streams:
            full_key = rconf.full_key(stream)
            try:
                # Get pending count
                pending_info = self.redis.client.xpending(full_key, group)
                if pending_info and isinstance(pending_info, dict):
                    pending = pending_info.get("pending", 0)
                    
                    # Get consumer count
                    groups = self.redis.client.xinfo_groups(full_key)
                    consumers = 0
                    for g in groups:
                        if g.get("name") == group:
                            consumers = g.get("consumers", 0)
                            break
                    
                    # Calculate pending per worker
                    per_worker = pending / consumers if consumers > 0 else pending
                    
                    if per_worker > 100:
                        print(f"🔴 {service:15} High load ({pending} pending / {consumers} workers = {per_worker:.0f} each)")
                        print(f"   → Recommend adding {max(1, int(pending / 100) - consumers)} more workers")
                    elif per_worker > 50:
                        print(f"🟡 {service:15} Moderate load ({pending} pending / {consumers} workers = {per_worker:.0f} each)")
                    elif consumers > 0:
                        print(f"🟢 {service:15} Normal ({pending} pending / {consumers} workers = {per_worker:.0f} each)")
            except Exception:
                pass
        
        print("\n=== Scale Workers ===\n")
        print("To add workers, run in separate terminals:")
        print("  python -m agent.operational_agents.rag_agent.worker")
        print("  python -m agent.operational_agents.persistence_agent.write_worker")
        print("  python -m agent.operational_agents.copywriter.worker")
        print()


def main():
    parser = argparse.ArgumentParser(description="Ops CLI - Unified operations tool")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Health command
    health_parser = subparsers.add_parser("health", help="Run health checks")
    health_parser.add_argument("--all", action="store_true", help="Show all metrics")
    health_parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    
    # Inspect command
    inspect_parser = subparsers.add_parser("inspect", help="Inspect stream")
    inspect_parser.add_argument("stream", help="Stream name (e.g., rag:tasks)")
    inspect_parser.add_argument("--count", type=int, default=5, help="Number of recent messages to show")
    inspect_parser.add_argument("--verbose", action="store_true", help="Show full message contents")
    
    # DLQ commands
    dlq_parser = subparsers.add_parser("dlq", help="DLQ operations")
    dlq_subparsers = dlq_parser.add_subparsers(dest="dlq_command", required=True)
    
    dlq_list_parser = dlq_subparsers.add_parser("list", help="List all DLQs")
    dlq_list_parser.add_argument("--verbose", action="store_true", help="Show recent errors")
    
    dlq_replay_parser = dlq_subparsers.add_parser("replay", help="Replay DLQ messages")
    dlq_replay_parser.add_argument("dlq", help="DLQ stream (e.g., persist:dlq)")
    dlq_replay_parser.add_argument("--limit", type=int, default=10, help="Max messages to replay")
    dlq_replay_parser.add_argument("--dry-run", action="store_true", help="Dry-run mode")
    dlq_replay_parser.add_argument("--auto-fix", action="store_true", help="Auto-fix duplicates with upsert")
    dlq_replay_parser.add_argument("--transient-only", action="store_true", help="Only retry transient errors")
    
    # Group commands
    group_parser = subparsers.add_parser("group", help="Consumer group operations")
    group_subparsers = group_parser.add_subparsers(dest="group_command", required=True)
    
    group_reset_parser = group_subparsers.add_parser("reset", help="Reset consumer group")
    group_reset_parser.add_argument("stream", help="Stream name")
    group_reset_parser.add_argument("group", help="Group name")
    group_reset_parser.add_argument("--id", default="$", help="Reset to ID (default: $)")
    
    group_claim_parser = group_subparsers.add_parser("claim", help="Claim stuck messages")
    group_claim_parser.add_argument("stream", help="Stream name")
    group_claim_parser.add_argument("group", help="Group name")
    group_claim_parser.add_argument("--idle-ms", type=int, default=300000, help="Min idle time (ms)")
    group_claim_parser.add_argument("--new-consumer", default="ops-cli", help="New consumer name")
    group_claim_parser.add_argument("--count", type=int, default=10, help="Max messages to claim")
    
    # Scale command
    scale_parser = subparsers.add_parser("scale", help="Worker scaling")
    scale_subparsers = scale_parser.add_subparsers(dest="scale_command", required=True)
    scale_info_parser = scale_subparsers.add_parser("info", help="Show scaling info")
    
    args = parser.parse_args()
    
    cli = OpsCLI()
    
    try:
        if args.command == "health":
            cli.health(args)
        elif args.command == "inspect":
            cli.inspect(args)
        elif args.command == "dlq":
            if args.dlq_command == "list":
                cli.dlq_list(args)
            elif args.dlq_command == "replay":
                cli.dlq_replay(args)
        elif args.command == "group":
            if args.group_command == "reset":
                cli.group_reset(args)
            elif args.group_command == "claim":
                cli.group_claim(args)
        elif args.command == "scale":
            if args.scale_command == "info":
                cli.scale_info(args)
    finally:
        cli.redis.close()


if __name__ == "__main__":
    main()
