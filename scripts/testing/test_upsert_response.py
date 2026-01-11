#!/usr/bin/env python
"""Test Supabase upsert to see what it returns."""
import os
import sys
import uuid
sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv()

from supabase import create_client

c = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

test_email = f"upsert_test_{uuid.uuid4().hex[:8]}@example.com"
record = {
    "email": test_email,
    "source": "test",
}

print(f"Testing upsert with email: {test_email}")
print(f"Record: {record}")
print()

# Test with on_conflict
print("=== Test 1: upsert with on_conflict=['email'] ===")
try:
    resp = c.table("staging_leads").upsert(record, on_conflict="email").execute()
    print(f"Response type: {type(resp)}")
    print(f"Response data: {resp.data}")
except Exception as e:
    print(f"Error: {e}")

print()

# Test without on_conflict
print("=== Test 2: upsert without on_conflict ===")
test_email2 = f"upsert_test2_{uuid.uuid4().hex[:8]}@example.com"
record2 = {"email": test_email2, "source": "test"}
try:
    resp = c.table("staging_leads").upsert(record2).execute()
    print(f"Response type: {type(resp)}")
    print(f"Response data: {resp.data}")
except Exception as e:
    print(f"Error: {e}")
