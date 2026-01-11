"""Query workflow state tracking for orchestrator commands.

Displays in-flight workflows, completion status, and task counts.
Requires WORKFLOW_STATE_ENABLED=1 in environment.
"""
import argparse
import json
from typing import List, Dict, Any

from services.redis import RedisStreamsClient as RedisPubSub
from agent.tools.redis import config as rconf


def get_workflow_state(correlation_id: str) -> Dict[str, Any]:
    """Get workflow state for a specific correlation ID."""
    r = RedisPubSub()
    state_key = rconf.full_key(rconf.workflow_state_key(correlation_id))
    state_data = r.client.hgetall(state_key)
    
    if not state_data:
        return {}
    
    # Decode bytes to strings
    decoded = {k.decode() if isinstance(k, bytes) else k: 
               v.decode() if isinstance(v, bytes) else v 
               for k, v in state_data.items()}
    
    # Parse JSON details if present
    if "details" in decoded:
        try:
            decoded["details"] = json.loads(decoded["details"])
        except:
            pass
    
    return decoded


def list_all_workflow_states() -> List[Dict[str, Any]]:
    """List all active workflow states by scanning workflow:state:* keys."""
    r = RedisPubSub()
    pattern = rconf.full_key("workflow:state:*")
    
    keys = r.client.keys(pattern)
    states = []
    
    for key in keys:
        key_str = key.decode() if isinstance(key, bytes) else key
        # Extract correlation_id from key
        correlation_id = key_str.split("workflow:state:")[-1]
        state = r.client.hgetall(key)
        
        if state:
            decoded = {k.decode() if isinstance(k, bytes) else k: 
                      v.decode() if isinstance(v, bytes) else v 
                      for k, v in state.items()}
            
            if "details" in decoded:
                try:
                    decoded["details"] = json.loads(decoded["details"])
                except:
                    pass
            
            # Add TTL info
            ttl = r.client.ttl(key)
            decoded["ttl_seconds"] = ttl if ttl > 0 else None
            
            states.append(decoded)
    
    return states


def print_workflow_state(state: Dict[str, Any], verbose: bool = False) -> None:
    """Pretty print a workflow state."""
    if not state:
        print("No workflow state found")
        return
    
    print(f"\n{'='*80}")
    print(f"Correlation ID: {state.get('correlation_id', 'N/A')}")
    print(f"Status: {state.get('status', 'N/A')}")
    print(f"Orchestrator: {state.get('orchestrator_id', 'N/A')}")
    print(f"Last Updated: {state.get('last_updated', 'N/A')}")
    
    task_count = state.get('task_count')
    completed_count = state.get('completed_count')
    
    if task_count:
        completed = completed_count or '0'
        print(f"Progress: {completed}/{task_count} tasks")
    
    if state.get('ttl_seconds'):
        print(f"TTL: {state['ttl_seconds']}s remaining")
    
    if verbose and state.get('details'):
        print(f"\nDetails:")
        details = state['details']
        if isinstance(details, dict):
            for k, v in details.items():
                print(f"  {k}: {v}")
        else:
            print(f"  {details}")
    
    print(f"{'='*80}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Query workflow state tracking")
    parser.add_argument(
        "--correlation-id",
        help="Get state for a specific correlation ID"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all active workflow states"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed state information"
    )
    
    args = parser.parse_args()
    
    if not rconf.WORKFLOW_STATE_ENABLED:
        print("⚠️  Workflow state tracking is DISABLED")
        print("   Set WORKFLOW_STATE_ENABLED=1 in your environment to enable")
        return 1
    
    if args.correlation_id:
        state = get_workflow_state(args.correlation_id)
        if state:
            print_workflow_state(state, verbose=args.verbose)
        else:
            print(f"No workflow state found for correlation_id: {args.correlation_id}")
    
    elif args.list:
        states = list_all_workflow_states()
        if not states:
            print("No active workflow states found")
            return 0
        
        print(f"\nFound {len(states)} active workflow(s):\n")
        for state in states:
            print_workflow_state(state, verbose=args.verbose)
    
    else:
        parser.print_help()
        return 1
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
