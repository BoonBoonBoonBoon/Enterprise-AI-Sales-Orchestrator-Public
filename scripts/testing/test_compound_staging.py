#!/usr/bin/env python
"""Test compound staging_leads write with injected campaign_id."""
import os
import sys
import uuid
from pathlib import Path
from dotenv import load_dotenv

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
load_dotenv()

from services.persistence.adapters.supabase_adapter import SupabaseAdapter

def test_compound_staging_write():
    """Simulate what _inject_scoping_fields should do for compound payloads."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    
    if not url or not key:
        print("ERROR: Missing SUPABASE_URL or SUPABASE_KEY")
        return False
    
    # Create adapter (no table_name param - passed per-operation)
    adapter = SupabaseAdapter(url=url, key=key)
    
    # Simulate the injected record (what _inject_scoping_fields now does)
    # Placeholder campaign_id can be overridden with CAMPAIGN_ID_PLACEHOLDER env
    campaign_placeholder = os.getenv("CAMPAIGN_ID_PLACEHOLDER", "9646f98a-e987-4a8c-b786-9b82ea985d38")
    # Use UUID5 for deterministic client_id (same as persistence_agent.py line 86)
    client_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, "agentic-dev"))
    test_id = str(uuid.uuid4())
    test_email = f"test-compound-{uuid.uuid4().hex[:8]}@example.com"
    
    # This is what a compound payload would look like AFTER injection
    # campaign_id is intentionally omitted (NULL) for inbound/unsolicited leads
    record = {
        "id": test_id,
        "email": test_email,
        "client_id": client_uuid,  # Injected by _inject_scoping_fields
        "campaign_id": campaign_placeholder,  # Placeholder until real campaign is linked
        "source": "compound_test",
        "enrichment_status": "pending",
    }
    
    print(f"Testing compound write with injected fields:")
    print(f"  - id: {test_id}")
    print(f"  - email: {test_email}")
    print(f"  - client_id: {record['client_id']}")
    print(f"  - campaign_id: {record['campaign_id']}")
    
    try:
        result = adapter.write("staging_leads", record)
        print(f"\n✅ SUCCESS! Record written to Supabase staging_leads")
        print(f"Result: {result}")
        
        # Clean up test data
        try:
            adapter.delete("staging_leads", test_id)
            print(f"Cleaned up test record: {test_id}")
        except Exception as e:
            print(f"Note: Cleanup skipped - {e}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        return False

if __name__ == "__main__":
    success = test_compound_staging_write()
    sys.exit(0 if success else 1)
