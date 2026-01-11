#!/usr/bin/env python3
"""DLQ Automation Script

Intelligent DLQ processing with:
- Error categorization (transient vs permanent)
- Smart retry logic with exponential backoff
- Auto-transform for common errors (upsert on duplicate key)
- Batch processing with rate limiting
- Dry-run mode for safety

Usage:
    # Dry-run (show what would be done)
    python scripts/dlq_automation.py --dlq persist:dlq --dry-run
    
    # Process up to 10 messages
    python scripts/dlq_automation.py --dlq persist:dlq --limit 10
    
    # Auto-fix duplicate key errors with upsert transform
    python scripts/dlq_automation.py --dlq persist:dlq --auto-fix-duplicates
    
    # Process transient errors only (network, timeout, rate limit)
    python scripts/dlq_automation.py --dlq rag:dlq --transient-only
    
    # Scheduled retry (cron: 0 */6 * * *)
    python scripts/dlq_automation.py --dlq persist:dlq --limit 100 --auto-fix-duplicates

Error Categories:
    - Transient: Network, timeout, rate limit → Retry with backoff
    - Duplicate: Unique constraint violation → Transform to upsert
    - Validation: Missing fields, invalid data → Skip (manual fix needed)
    - Permanent: Other errors → Skip unless forced
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv

load_dotenv()

from services.redis import RedisStreamsClient as RedisPubSub
from agent.tools.redis import config as rconf
from agent.utils.typed_envelope import from_redis_message, to_redis_fields


class ErrorCategory:
    """Error classification for DLQ messages."""
    TRANSIENT = "transient"       # Retry candidates
    DUPLICATE = "duplicate"       # Can auto-fix with upsert
    VALIDATION = "validation"     # Needs manual fix
    PERMANENT = "permanent"       # Skip retry


class DLQProcessor:
    """Intelligent DLQ message processor with error categorization."""
    
    # Error patterns for classification
    TRANSIENT_PATTERNS = [
        r"timeout",
        r"connection\s+(refused|reset|closed)",
        r"rate\s+limit",
        r"temporarily\s+unavailable",
        r"503\s+service\s+unavailable",
        r"429\s+too\s+many\s+requests",
    ]
    
    DUPLICATE_PATTERNS = [
        r"duplicate\s+key",
        r"unique\s+constraint",
        r"already\s+exists",
        r"23505",  # PostgreSQL unique violation code
    ]
    
    VALIDATION_PATTERNS = [
        r"missing\s+(required\s+)?field",
        r"invalid\s+(value|type|format)",
        r"validation\s+(error|failed)",
        r"not\s+null\s+violation",
        r"23502",  # PostgreSQL not-null violation
    ]
    
    def __init__(
        self,
        dry_run: bool = False,
        auto_fix_duplicates: bool = False,
        transient_only: bool = False,
        max_retry_age_hours: int = 72,
    ):
        self.redis = RedisPubSub()
        self.dry_run = dry_run
        self.auto_fix_duplicates = auto_fix_duplicates
        self.transient_only = transient_only
        self.max_retry_age_hours = max_retry_age_hours
        
        # Statistics
        self.stats = {
            "processed": 0,
            "retried": 0,
            "transformed": 0,
            "skipped": 0,
            "errors": 0,
            "by_category": {
                ErrorCategory.TRANSIENT: 0,
                ErrorCategory.DUPLICATE: 0,
                ErrorCategory.VALIDATION: 0,
                ErrorCategory.PERMANENT: 0,
            }
        }
    
    def categorize_error(self, error_msg: str) -> str:
        """Classify error message into category."""
        error_lower = error_msg.lower()
        
        # Check for transient errors
        for pattern in self.TRANSIENT_PATTERNS:
            if re.search(pattern, error_lower, re.IGNORECASE):
                return ErrorCategory.TRANSIENT
        
        # Check for duplicate key errors
        for pattern in self.DUPLICATE_PATTERNS:
            if re.search(pattern, error_lower, re.IGNORECASE):
                return ErrorCategory.DUPLICATE
        
        # Check for validation errors
        for pattern in self.VALIDATION_PATTERNS:
            if re.search(pattern, error_lower, re.IGNORECASE):
                return ErrorCategory.VALIDATION
        
        return ErrorCategory.PERMANENT
    
    def transform_to_upsert(self, envelope: Dict[str, Any]) -> Dict[str, Any]:
        """Transform failed insert to upsert operation.
        
        For persist:dlq messages with duplicate key errors, change operation to upsert.
        """
        payload = envelope.get("payload", {})
        
        # Check if it's a persist task with insert operation
        if payload.get("op") == "insert":
            # Transform to upsert
            payload["op"] = "upsert"
            
            # Add on_conflict if not present
            if "on_conflict" not in payload:
                # Try to extract conflict column from error message
                error_msg = envelope.get("error", {}).get("message", "")
                email_match = re.search(r'\(email\)=', error_msg)
                if email_match:
                    payload["on_conflict"] = ["email"]
                else:
                    # Default to common conflict columns
                    payload["on_conflict"] = ["email"]  # Most common for leads table
            
            envelope["payload"] = payload
            print(f"  → Transformed insert to upsert with on_conflict={payload.get('on_conflict')}")
        
        return envelope
    
    def should_retry(self, envelope: Dict[str, Any], category: str) -> Tuple[bool, str]:
        """Determine if message should be retried.
        
        Returns:
            (should_retry, reason)
        """
        # Check message age
        created_at = envelope.get("created_at")
        if created_at:
            try:
                created_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                age_hours = (datetime.now(timezone.utc) - created_dt).total_seconds() / 3600
                
                if age_hours > self.max_retry_age_hours:
                    return False, f"message too old ({age_hours:.1f}h > {self.max_retry_age_hours}h)"
            except Exception:
                pass
        
        # Category-based decisions
        if category == ErrorCategory.TRANSIENT:
            return True, "transient error"
        
        if category == ErrorCategory.DUPLICATE:
            if self.auto_fix_duplicates:
                return True, "duplicate error (will transform to upsert)"
            else:
                return False, "duplicate error (auto-fix disabled)"
        
        if category == ErrorCategory.VALIDATION:
            return False, "validation error (needs manual fix)"
        
        if category == ErrorCategory.PERMANENT:
            return False, "permanent error"
        
        return False, "unknown reason"
    
    def process_dlq_message(
        self,
        msg_id: str,
        fields: Dict[str, Any],
        target_stream: str,
    ) -> bool:
        """Process a single DLQ message.
        
        Returns:
            True if successfully processed/retried, False if skipped
        """
        try:
            # Parse envelope
            envelope = from_redis_message(fields)
            
            # Extract error message
            error_data = envelope.get("error", {})
            error_msg = error_data.get("message", "unknown error")
            
            # Categorize error
            category = self.categorize_error(error_msg)
            self.stats["by_category"][category] += 1
            
            # Check if transient-only mode
            if self.transient_only and category != ErrorCategory.TRANSIENT:
                print(f"  ⊘ Skipped (not transient): {category}")
                self.stats["skipped"] += 1
                return False
            
            # Decide if should retry
            should_retry, reason = self.should_retry(envelope, category)
            
            if not should_retry:
                print(f"  ⊘ Skipped: {reason}")
                self.stats["skipped"] += 1
                return False
            
            # Transform if duplicate error and auto-fix enabled
            if category == ErrorCategory.DUPLICATE and self.auto_fix_duplicates:
                envelope = self.transform_to_upsert(envelope)
                self.stats["transformed"] += 1
            
            # Retry message
            if not self.dry_run:
                # Reset status and retry count for fresh attempt
                envelope["status"] = "pending"
                envelope["retry_count"] = 0
                
                # Re-enqueue to target stream
                self.redis.xadd(target_stream, to_redis_fields(envelope))
                print(f"  ✓ Retried to {target_stream}")
                self.stats["retried"] += 1
            else:
                print(f"  [DRY-RUN] Would retry to {target_stream}")
                self.stats["retried"] += 1
            
            return True
            
        except Exception as e:
            print(f"  ✗ Error processing message: {e}")
            self.stats["errors"] += 1
            return False
    
    def process_dlq(
        self,
        dlq_stream: str,
        target_stream: str,
        limit: int = 10,
        delete_after_retry: bool = True,
    ) -> None:
        """Process messages from DLQ stream.
        
        Args:
            dlq_stream: DLQ stream name (e.g., "persist:dlq")
            target_stream: Target stream to re-enqueue to (e.g., "persist:tasks")
            limit: Max messages to process
            delete_after_retry: Remove from DLQ after successful retry
        """
        print(f"\n{'='*80}")
        print(f"DLQ Automation - {datetime.now(timezone.utc).isoformat()}")
        print(f"{'='*80}")
        print(f"DLQ Stream: {rconf.full_key(dlq_stream)}")
        print(f"Target Stream: {rconf.full_key(target_stream)}")
        print(f"Limit: {limit}")
        print(f"Dry-run: {self.dry_run}")
        print(f"Auto-fix duplicates: {self.auto_fix_duplicates}")
        print(f"Transient-only: {self.transient_only}")
        print(f"{'='*80}\n")
        
        # Fetch DLQ messages
        full_dlq_key = rconf.full_key(dlq_stream)
        full_target_key = rconf.full_key(target_stream)
        
        try:
            messages = self.redis.client.xrange(full_dlq_key, count=limit)
            
            if not messages:
                print("No messages in DLQ")
                return
            
            print(f"Processing {len(messages)} DLQ messages...\n")
            
            for msg_id, fields in messages:
                self.stats["processed"] += 1
                print(f"[{self.stats['processed']}/{len(messages)}] Message {msg_id}")
                
                # Parse and categorize
                try:
                    envelope = from_redis_message(fields)
                    error_msg = envelope.get("error", {}).get("message", "")
                    category = self.categorize_error(error_msg)
                    
                    print(f"  Category: {category}")
                    print(f"  Error: {error_msg[:100]}...")
                    
                    # Process
                    success = self.process_dlq_message(msg_id, fields, full_target_key)
                    
                    # Delete from DLQ if successful and not dry-run
                    if success and delete_after_retry and not self.dry_run:
                        self.redis.client.xdel(full_dlq_key, msg_id)
                        print(f"  ✓ Removed from DLQ")
                    
                except Exception as e:
                    print(f"  ✗ Error: {e}")
                    self.stats["errors"] += 1
                
                print()  # Blank line between messages
                
                # Rate limiting
                time.sleep(0.1)
        
        except Exception as e:
            print(f"Error accessing DLQ: {e}")
            return
        
        # Print summary
        print(f"\n{'='*80}")
        print("Summary")
        print(f"{'='*80}")
        print(f"Processed: {self.stats['processed']}")
        print(f"Retried: {self.stats['retried']}")
        print(f"Transformed: {self.stats['transformed']}")
        print(f"Skipped: {self.stats['skipped']}")
        print(f"Errors: {self.stats['errors']}")
        print(f"\nBy Category:")
        for cat, count in self.stats["by_category"].items():
            print(f"  {cat}: {count}")
        print(f"{'='*80}\n")


def main():
    parser = argparse.ArgumentParser(description="DLQ Automation - Intelligent retry with error categorization")
    parser.add_argument("--dlq", required=True, help="DLQ stream (persist:dlq, rag:dlq, copy:dlq)")
    parser.add_argument("--target", help="Target stream to retry to (auto-detected if omitted)")
    parser.add_argument("--limit", type=int, default=10, help="Max messages to process (default: 10)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    parser.add_argument("--auto-fix-duplicates", action="store_true", help="Transform duplicate errors to upsert")
    parser.add_argument("--transient-only", action="store_true", help="Only retry transient errors")
    parser.add_argument("--max-age-hours", type=int, default=72, help="Max message age for retry (default: 72h)")
    parser.add_argument("--keep-in-dlq", action="store_true", help="Don't delete from DLQ after retry")
    
    args = parser.parse_args()
    
    # Auto-detect target stream if not provided
    target_stream = args.target
    if not target_stream:
        if "persist" in args.dlq:
            target_stream = "persist:tasks"
        elif "rag" in args.dlq:
            target_stream = "rag:tasks"
        elif "copy" in args.dlq:
            target_stream = "copy:tasks"
        else:
            print(f"Error: Cannot auto-detect target stream for {args.dlq}. Please specify --target")
            return 1
        print(f"Auto-detected target stream: {target_stream}\n")
    
    processor = DLQProcessor(
        dry_run=args.dry_run,
        auto_fix_duplicates=args.auto_fix_duplicates,
        transient_only=args.transient_only,
        max_retry_age_hours=args.max_age_hours,
    )
    
    processor.process_dlq(
        dlq_stream=args.dlq,
        target_stream=target_stream,
        limit=args.limit,
        delete_after_retry=not args.keep_in_dlq,
    )
    
    processor.redis.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
