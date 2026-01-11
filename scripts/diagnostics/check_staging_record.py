#!/usr/bin/env python
"""Check staging_leads for test record."""
import sys
import os
sys.path.insert(0, ".")
from services.persistence.adapters.supabase_adapter import SupabaseAdapter
from dotenv import load_dotenv
load_dotenv()

url = os.environ.get("SUPABASE_URL", "")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_ANON_KEY", "")
adapter = SupabaseAdapter(url=url, key=key)
result = adapter.query("staging_leads", {"email": "staging_test_613e6fbc@example.com"}, limit=10)
print("Raw result type:", type(result))
print("Raw result:", result)
data = result if isinstance(result, list) else result.get("data", [])
print("Found:", len(data), "record(s)")
for r in data:
    print(f"  id={r.get('id')}")
    print(f"  email={r.get('email')}")
    print(f"  created_at={r.get('created_at')}")
