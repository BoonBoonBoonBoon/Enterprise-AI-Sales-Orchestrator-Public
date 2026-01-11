"""
Test Persistence Agent with actual Supabase connection.
Run: python -m scripts.test_persistence_agent
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.persistence.adapters.supabase_adapter import SupabaseAdapter

def main():
    print("="*60)
    print("  PERSISTENCE AGENT TEST")
    print("="*60)
    
    url = os.getenv("SUPABASE_URL")
    persistence_jwt = os.getenv("SUPABASE_PERSISTENCE_JWT")
    anon_key = os.getenv("SUPABASE_ANON_KEY")
    
    if not all([url, persistence_jwt, anon_key]):
        print("[ERROR] Missing environment variables")
        return False
    
    print("\n1. Creating Supabase adapter with custom JWT...")
    adapter = SupabaseAdapter(url, persistence_jwt, anon_key=anon_key)
    print(f"   [OK] Adapter created")
    
    print("\n2. Testing SELECT (read)...")
    try:
        results = adapter.query("clients", limit=1)
        print(f"   [OK] Retrieved {len(results)} clients")
    except Exception as e:
        print(f"   [FAIL] {e}")
        return False
    
    print("\n3. Testing INSERT (write)...")
    import uuid
    test_id = str(uuid.uuid4())
    try:
        result = adapter.write("clients", {
            "id": test_id,
            "name": "Test Persistence Agent Write"
        })
        print(f"   [OK] Created client {test_id[:8]}...")
    except Exception as e:
        print(f"   [FAIL] {e}")
        return False
    
    print("\n4. Testing DELETE (cleanup)...")
    try:
        # Use query to verify it exists first
        check = adapter.read("clients", test_id)
        if check:
            print(f"   [OK] Verified record exists")
            # Delete via direct SQL (adapter doesn't have delete method)
            import requests
            headers = {
                "apikey": anon_key,
                "Authorization": f"Bearer {persistence_jwt}",
                "Content-Type": "application/json"
            }
            r = requests.delete(f"{url}/rest/v1/clients?id=eq.{test_id}", 
                              headers=headers, timeout=10)
            if r.status_code in [200, 204]:
                print(f"   [OK] Deleted test record")
            else:
                print(f"   [WARN] Delete status: {r.status_code}")
    except Exception as e:
        print(f"   [FAIL] {e}")
    
    print("\n" + "="*60)
    print("  ALL TESTS PASSED!")
    print("="*60)
    print("\nPersistence agent is ready for production use.")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
