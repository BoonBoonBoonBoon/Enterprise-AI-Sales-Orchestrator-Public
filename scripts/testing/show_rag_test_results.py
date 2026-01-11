#!/usr/bin/env python
"""Display results from our test RAG enrichment tasks."""

import sys
import json
from pathlib import Path
from datetime import datetime

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


def display_test_results(tenant_id: str = "agentic-dev"):
    """Display results from our 3 test tasks."""
    
    redis_client = RedisPubSub().client
    result_stream = f"{tenant_id}:agents:rag:results"
    
    print(f"""
╔════════════════════════════════════════════════════════════════════╗
║  RAG Agent Test Results - Our 3 Tasks                              ║
╚════════════════════════════════════════════════════════════════════╝

We sent 3 mock enrichment tasks demonstrating different scenarios:

1. ✅ VALID lead (≥0.7 completeness)
   └─ Expected: Deterministic path, fast enrichment via vectors + APIs
   
2. 🔧 PARTIAL lead (0.3-0.7 completeness)
   └─ Expected: LLM repair attempt, max 2 tries
   
3. ❌ HOPELESS lead (<0.3 completeness)
   └─ Expected: Error path, no LLM repair attempted
""")
    
    # Get all results
    all_results = redis_client.xrange(result_stream)
    
    if not all_results:
        print("No results found in stream yet.")
        return
    
    print(f"Total results in stream: {len(all_results)}")
    
    # Parse and display last few results (our tasks should be recent)
    print(f"\n📊 Last 5 Results:")
    print(f"{'='*70}")
    
    recent = list(reversed(all_results[-5:]))
    for i, (msg_id, fields) in enumerate(recent, 1):
        try:
            # Decode fields
            decoded_fields = {}
            for k, v in fields.items():
                key = k.decode() if isinstance(k, bytes) else k
                val = v.decode() if isinstance(v, bytes) else v
                decoded_fields[key] = val
            
            # Try to parse payload as JSON
            try:
                payload = json.loads(decoded_fields.get('payload', '{}'))
                is_valid_json = True
            except:
                payload = {}
                is_valid_json = False
            
            print(f"\n{i}. Message ID: {msg_id.decode() if isinstance(msg_id, bytes) else msg_id}")
            print(f"   Status: {decoded_fields.get('status', 'UNKNOWN')}")
            print(f"   Source: {decoded_fields.get('source', 'N/A')}")
            
            # Display payload info
            if is_valid_json and payload:
                if 'validation_result' in payload:
                    val = payload['validation_result']
                    print(f"   Validation:")
                    print(f"     - Completeness: {val.get('completeness_score', 'N/A')}")
                    print(f"     - Valid: {val.get('is_valid', 'N/A')}")
                    print(f"     - Can Use Deterministic: {val.get('can_use_deterministic', 'N/A')}")
                
                if 'enriched_data' in payload:
                    enrich = payload['enriched_data']
                    print(f"   Enrichment:")
                    print(f"     - Confidence: {enrich.get('confidence', 'N/A')}")
                    print(f"     - Sources: {enrich.get('sources', [])}")
                
                if 'repair_result' in payload:
                    repair = payload['repair_result']
                    print(f"   Repair:")
                    print(f"     - Strategy: {repair.get('repair_strategy', 'N/A')}")
                    print(f"     - Confidence: {repair.get('confidence', 'N/A')}")
        
        except Exception as e:
            print(f"\n{i}. [Error parsing result: {str(e)[:50]}]")
    
    print(f"\n{'='*70}\n")


if __name__ == "__main__":
    display_test_results()
