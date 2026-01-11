#!/usr/bin/env python
"""Test Supabase upsert with client_id and campaign_id to see exact response."""
import os
import sys
import uuid
sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv()

from supabase import create_client

c = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

test_email = f"full_upsert_test_{uuid.uuid4().hex[:8]}@example.com"
client_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, "agentic-dev"))
campaign_id = "9646f98a-e987-4a8c-b786-9b82ea985d38"

record = {
    "email": test_email,
    "source": "inbound_email",
    "client_id": client_uuid,
    "campaign_id": campaign_id,
}

print(f"Testing upsert with full record:")
print(f"  email: {test_email}")
print(f"  client_id: {client_uuid}")
print(f"  campaign_id: {campaign_id}")
print()

# Test upsert (without on_conflict, like the compound handler does)
print("=== Upsert without on_conflict ===")
try:
    resp = c.table("staging_leads").upsert(record).execute()
    print(f"Response type: {type(resp)}")
    print(f"Response data type: {type(resp.data)}")
    print(f"Response data: {resp.data}")
    if resp.data:
        print(f"  First record id: {resp.data[0].get('id')}")
except Exception as e:
    print(f"Error: {e}")
