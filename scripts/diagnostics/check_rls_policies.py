#!/usr/bin/env python
"""Check RLS policies via Supabase."""
import os
import sys
sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv()
import requests

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")  # service_role key

headers = {
    "apikey": key,
    "Authorization": f"Bearer {key}",
    "Content-Type": "application/json",
}

# Query pg_policies directly
sql = """
SELECT tablename, policyname, permissive, roles, cmd, qual, with_check
FROM pg_policies 
WHERE schemaname = 'public' 
AND tablename IN ('staging_leads', 'staging_conversations', 'staging_messages')
ORDER BY tablename, policyname;
"""

# Use PostgREST RPC endpoint
response = requests.post(
    f"{url}/rest/v1/rpc/exec_sql",
    headers=headers,
    json={"sql_query": sql}
)

if response.status_code == 200:
    print("Policies:")
    print(response.json())
else:
    print(f"RPC failed: {response.status_code}")
    print(response.text)
    
    # Try alternative: use pg_meta if available
    print("\n=== Trying pg_meta API ===")
    meta_response = requests.get(
        f"{url}/pg/tables?schema=public",
        headers=headers
    )
    print(meta_response.status_code, meta_response.text[:500] if meta_response.text else "")
