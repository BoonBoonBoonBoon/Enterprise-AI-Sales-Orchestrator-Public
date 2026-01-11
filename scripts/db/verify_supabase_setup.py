"""
Verify Supabase RLS setup and JWT tokens are working correctly.
Run: python -m scripts.verify_supabase_setup
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

def print_header(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")

def print_result(test_name, passed, details=""):
    status = "[PASS]" if passed else "[FAIL]"
    print(f"{status} {test_name}")
    if details:
        print(f"       {details}")

def main():
    print_header("SUPABASE SETUP VERIFICATION")
    
    # Check 1: Environment variables
    print_header("Step 1: Checking Environment Variables")
    
    supabase_url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
    anon_key = os.getenv("SUPABASE_ANON_KEY")
    rag_jwt = os.getenv("SUPABASE_RAG_JWT")
    persistence_jwt = os.getenv("SUPABASE_PERSISTENCE_JWT")
    
    print_result("SUPABASE_URL", bool(supabase_url), supabase_url[:50] + "..." if supabase_url else "MISSING")
    print_result("SUPABASE_SERVICE_KEY", bool(service_key), "***" + service_key[-10:] if service_key else "MISSING")
    print_result("SUPABASE_ANON_KEY", bool(anon_key), "***" + anon_key[-10:] if anon_key else "MISSING")
    print_result("SUPABASE_RAG_JWT", bool(rag_jwt), "***" + rag_jwt[-20:] if rag_jwt else "MISSING")
    print_result("SUPABASE_PERSISTENCE_JWT", bool(persistence_jwt), "***" + persistence_jwt[-20:] if persistence_jwt else "MISSING")
    
    if not all([supabase_url, anon_key, rag_jwt, persistence_jwt]):
        print("\n[ERROR] Missing required environment variables. Check .env file.")
        return False
    
    # Check 2: Test RAG JWT (READ)
    print_header("Step 2: Testing RAG JWT (Read-Only)")
    
    try:
        import requests
        
        # Use REST API with anon key + custom JWT pattern
        headers_rag = {
            "apikey": anon_key,
            "Authorization": f"Bearer {rag_jwt}",
            "Content-Type": "application/json"
        }
        
        # Try SELECT (should work)
        try:
            r = requests.get(f"{supabase_url}/rest/v1/clients?select=id&limit=1", headers=headers_rag, timeout=10)
            if r.status_code == 200:
                data = r.json()
                print_result("RAG SELECT clients", True, f"Returned {len(data)} rows")
            else:
                print_result("RAG SELECT clients", False, f"Status {r.status_code}: {r.text[:80]}")
        except Exception as e:
            print_result("RAG SELECT clients", False, str(e)[:80])
        
        # Try INSERT (should fail - read only)
        try:
            r = requests.post(f"{supabase_url}/rest/v1/clients", 
                            headers=headers_rag, 
                            json={"name": "TEST_SHOULD_FAIL"},
                            timeout=10)
            if r.status_code in [401, 403]:
                print_result("RAG INSERT blocked", True, "Correctly rejected by RLS")
            else:
                print_result("RAG INSERT blocked", False, f"Status {r.status_code} - should have been blocked!")
        except Exception as e:
            print_result("RAG INSERT blocked", False, str(e)[:80])
                
    except Exception as e:
        print_result("RAG JWT connection", False, str(e)[:80])
    
    # Check 3: Test Persistence JWT (WRITE)
    print_header("Step 3: Testing Persistence JWT (Read/Write)")
    
    try:
        import requests
        
        # Use REST API with anon key + custom JWT pattern
        headers_persist = {
            "apikey": anon_key,
            "Authorization": f"Bearer {persistence_jwt}",
            "Content-Type": "application/json"
        }
        
        # Try SELECT (should work)
        try:
            r = requests.get(f"{supabase_url}/rest/v1/clients?select=id&limit=1", headers=headers_persist, timeout=10)
            if r.status_code == 200:
                data = r.json()
                print_result("Persistence SELECT clients", True, f"Returned {len(data)} rows")
            else:
                print_result("Persistence SELECT clients", False, f"Status {r.status_code}: {r.text[:80]}")
        except Exception as e:
            print_result("Persistence SELECT clients", False, str(e)[:80])
        
        # Try INSERT (should work)
        import uuid
        test_id = str(uuid.uuid4())
        try:
            r = requests.post(f"{supabase_url}/rest/v1/clients",
                            headers=headers_persist,
                            json={"id": test_id, "name": "TEST_PERSISTENCE_AGENT"},
                            timeout=10)
            if r.status_code in [200, 201]:
                print_result("Persistence INSERT clients", True, f"Created client {test_id[:8]}...")
                
                # Clean up - DELETE the test record
                r_del = requests.delete(f"{supabase_url}/rest/v1/clients?id=eq.{test_id}",
                                      headers=headers_persist,
                                      timeout=10)
                if r_del.status_code in [200, 204]:
                    print_result("Persistence DELETE clients", True, "Cleaned up test record")
            else:
                print_result("Persistence INSERT clients", False, f"Status {r.status_code}: {r.text[:80]}")
            
        except Exception as e:
            print_result("Persistence INSERT clients", False, str(e)[:80])
                
    except Exception as e:
        print_result("Persistence JWT connection", False, str(e)[:80])
    
    # Check 4: Test client record exists for agents
    print_header("Step 4: Checking Test Client Record")
    
    try:
        test_client_id = "93d28de3-2835-52f3-b2ef-c2eb8a2ac09b"
        r = requests.get(f"{supabase_url}/rest/v1/clients?id=eq.{test_client_id}",
                        headers=headers_persist,
                        timeout=10)
        
        if r.status_code == 200:
            data = r.json()
            if data:
                print_result("Test client exists", True, f"Name: {data[0].get('name', 'N/A')}")
            else:
                print_result("Test client exists", False, "Run create_test_client.sql in Supabase")
        else:
            print_result("Test client check", False, f"Status {r.status_code}: {r.text[:80]}")
            
    except Exception as e:
        print_result("Test client check", False, str(e)[:80])
    
    # Summary
    print_header("SETUP COMPLETE")
    print("""
Next steps:
1. If all tests passed, run the Persistence Agent test:
   python -m tiers.tier_3.persistence_agent.tests.direct_test

2. If RAG INSERT was NOT blocked, check RLS policies in Supabase

3. If test client is missing, run in Supabase SQL Editor:
   INSERT INTO clients (id, name) VALUES 
   ('93d28de3-2835-52f3-b2ef-c2eb8a2ac09b', 'Agentic Dev Tenant');
    """)
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
