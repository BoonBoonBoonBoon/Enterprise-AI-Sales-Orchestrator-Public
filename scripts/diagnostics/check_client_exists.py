#!/usr/bin/env python
"""Check if client_uuid exists in clients table."""
import os
import sys
import uuid
sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv()

from supabase import create_client

c = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

client_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, "agentic-dev"))
print(f"Looking for client_id: {client_uuid}")

result = c.table("clients").select("*").eq("id", client_uuid).execute()
if result.data:
    print(f"Found client: {result.data[0]}")
else:
    print("Client NOT FOUND!")
    print("Listing all clients:")
    all_clients = c.table("clients").select("id,name").limit(10).execute()
    for client in all_clients.data:
        print(f"  {client}")
