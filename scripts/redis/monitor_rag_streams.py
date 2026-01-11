#!/usr/bin/env python
"""Monitor RAG agent Redis streams in real-time."""

import sys
import time
import json
from pathlib import Path
from typing import Optional

# Add project root to path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

try:
    from services.redis import RedisPubSub
except ImportError:
    from services.redis import RedisStreamsClient as RedisPubSub

from core.envelope import from_redis_message


def monitor_streams(tenant_id: str = "agentic-dev", duration: int = 60):
    """Monitor RAG agent streams for activity."""
    
    redis_client = RedisPubSub().client
    task_stream = f"{tenant_id}:agents:rag:tasks"
    result_stream = f"{tenant_id}:agents:rag:results"
    
    print(f"""
╔════════════════════════════════════════════════════════════════════╗
║  RAG Agent Stream Monitor                                          ║
╚════════════════════════════════════════════════════════════════════╝

Monitoring:
  Task Stream: {task_stream}
  Result Stream: {result_stream}
  Duration: {duration}s

Watching for:
  📤 Pending tasks in task stream
  📥 Completed enrichments in result stream
  ⏱️  Processing time per task
""")
    
    start_time = time.time()
    last_task_count = 0
    last_result_count = 0
    
    try:
        while time.time() - start_time < duration:
            # Get stream lengths
            task_count = redis_client.xlen(task_stream)
            result_count = redis_client.xlen(result_stream)
            
            # Display status
            elapsed = int(time.time() - start_time)
            print(f"\r[{elapsed:02d}s] Tasks: {task_count} | Results: {result_count}", end="", flush=True)
            
            # Check for newly completed results
            if result_count > last_result_count:
                new_results = result_count - last_result_count
                print(f"\n✅ {new_results} new result(s) available!")
                
                # Show recent results
                latest = redis_client.xrevrange(result_stream, count=new_results)
                for msg_id, fields in latest:
                    try:
                        env = from_redis_message(fields)
                        task_id = env.metadata.get("original_task_id", "unknown")
                        status = env.status
                        print(f"   Task {task_id[:8]}... → {status}")
                    except Exception as e:
                        print(f"   Error parsing result: {e}")
                
                last_result_count = result_count
                print(f"[{elapsed:02d}s] Tasks: {task_count} | Results: {result_count}", end="", flush=True)
            
            # Check task completion
            if task_count < last_task_count:
                completed = last_task_count - task_count
                print(f"\n🎉 {completed} task(s) completed!")
                print(f"[{elapsed:02d}s] Tasks: {task_count} | Results: {result_count}", end="", flush=True)
            
            last_task_count = task_count
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\n\n⏹️  Monitoring stopped by user")
    
    # Final summary
    print(f"\n\n{'='*70}")
    print(f"Final Status:")
    print(f"{'='*70}")
    final_tasks = redis_client.xlen(task_stream)
    final_results = redis_client.xlen(result_stream)
    print(f"Pending tasks: {final_tasks}")
    print(f"Completed results: {final_results}")
    
    if final_results > 0:
        print(f"\nLatest results:")
        latest = redis_client.xrevrange(result_stream, count=5)
        for i, (msg_id, fields) in enumerate(latest, 1):
            try:
                env = from_redis_message(fields)
                task_id = env.metadata.get("original_task_id", "unknown")
                status = env.status
                timestamp = env.metadata.get("retrieved_at", "unknown")
                print(f"  {i}. Task {task_id[:8]}... → {status} ({timestamp})")
            except Exception as e:
                print(f"  {i}. Error parsing result")
    
    print(f"\n{'='*70}\n")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Monitor RAG agent Redis streams")
    parser.add_argument("--duration", type=int, default=60, help="Monitor duration (seconds)")
    parser.add_argument("--tenant", default="agentic-dev", help="Tenant ID")
    args = parser.parse_args()
    
    monitor_streams(tenant_id=args.tenant, duration=args.duration)
