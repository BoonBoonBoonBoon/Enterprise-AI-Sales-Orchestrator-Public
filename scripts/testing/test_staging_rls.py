#!/usr/bin/env python
"""Apply RLS policies to staging tables via Supabase."""
import os
import sys
sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

from supabase import create_client

client = create_client(url, key)

sql = """
-- Check existing policies on staging tables
SELECT tablename, policyname, permissive, roles, cmd 
FROM pg_policies 
WHERE schemaname = 'public' 
AND tablename IN ('staging_leads', 'staging_conversations', 'staging_messages')
ORDER BY tablename, policyname;
"""

print("=== Checking existing RLS policies ===")
try:
    result = client.rpc("exec_sql", {"sql_query": sql}).execute()
    print(result)
except Exception as e:
    print(f"RPC failed: {e}")
    print()
    print("Trying direct query...")
    
# Try a simple insert to test permissions
print("\n=== Testing direct insert to staging_conversations ===")
try:
    # First we need a staging_lead
    lead_result = client.table("staging_leads").select("id").limit(1).execute()
    if lead_result.data:
        staging_lead_id = lead_result.data[0]["id"]
        print(f"Found staging_lead: {staging_lead_id}")
        
        # Try to insert a staging_conversation
        conv_result = client.table("staging_conversations").insert({
            "staging_lead_id": staging_lead_id,
            "thread_id": "test-thread",
            "subject": "Test from RLS check",
            "channel": "email",
            "status": "open",
            "metadata": {},
        }).execute()
        print(f"Insert succeeded: {conv_result.data}")
        
        # Clean up
        if conv_result.data:
            conv_id = conv_result.data[0]["id"]
            client.table("staging_conversations").delete().eq("id", conv_id).execute()
            print("Cleaned up test record")
    else:
        print("No staging_leads found - creating one first")
except Exception as e:
    print(f"Insert failed: {e}")
