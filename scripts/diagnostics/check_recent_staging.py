#!/usr/bin/env python
"""Check recent staging_leads in Supabase."""
import os
import sys
sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv()

from supabase import create_client

c = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
result = c.table("staging_leads").select("*").order("created_at", desc=True).limit(10).execute()
print("Recent staging_leads:")
for r in result.data:
    print(f"  {r['email']}, source={r.get('source')}, client_id={r.get('client_id')}, campaign_id={r.get('campaign_id')}")
