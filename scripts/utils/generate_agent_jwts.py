"""
Generate JWT tokens for RAG and Persistence agents locally.

This creates the same tokens the Edge Function would create,
but runs locally using your SUPABASE_SERVICE_KEY.

Run: python scripts/generate_agent_jwts.py
"""

import os
import json
import hmac
import hashlib
import base64
import time
from dotenv import load_dotenv

def base64url_encode(data):
    """Encode data as base64url (no padding)."""
    if isinstance(data, str):
        data = data.encode('utf-8')
    elif isinstance(data, dict):
        data = json.dumps(data, separators=(',', ':')).encode('utf-8')
    
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')

def sign_jwt(payload, secret):
    """Sign a JWT using HS256."""
    header = {"alg": "HS256", "typ": "JWT"}
    
    # Encode header and payload
    encoded_header = base64url_encode(header)
    encoded_payload = base64url_encode(payload)
    
    # Create signature
    message = f"{encoded_header}.{encoded_payload}"
    signature = hmac.new(
        secret.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).digest()
    
    encoded_signature = base64.urlsafe_b64encode(signature).rstrip(b'=').decode('utf-8')
    
    return f"{message}.{encoded_signature}"

# Load environment
load_dotenv()

service_key = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_KEY')
if not service_key:
    print("ERROR: SUPABASE_SERVICE_KEY or SUPABASE_KEY not found in .env")
    exit(1)

# Current timestamp
now = int(time.time())

# Get Supabase project reference from URL
supabase_url = os.getenv('SUPABASE_URL', '')
supabase_ref = supabase_url.replace('https://', '').replace('.supabase.co', '') if supabase_url else 'supabase'

# Create RAG Agent token (reader)
# Must include: iss, role, iat (Supabase required fields)
rag_payload = {
    "iss": "supabase",
    "ref": supabase_ref,
    "role": "authenticated",  # Supabase role (required)
    "sub": "rag-agent-service",
    "user_role": "agent_reader",  # Custom claim for RLS policies
    "iat": now
}

# Create Persistence Agent token (writer)
persistence_payload = {
    "iss": "supabase",
    "ref": supabase_ref,
    "role": "authenticated",  # Supabase role (required)
    "sub": "persistence-agent-service",
    "user_role": "agent_writer",  # Custom claim for RLS policies
    "iat": now
}

# Generate tokens
rag_token = sign_jwt(rag_payload, service_key)
persistence_token = sign_jwt(persistence_payload, service_key)

print("\n" + "="*80)
print("AGENT JWT TOKENS GENERATED")
print("="*80)
print("\nAdd these to your .env file:\n")
print("# RAG Agent (READ ONLY)")
print(f"SUPABASE_RAG_JWT={rag_token}\n")
print("# Persistence Agent (WRITE)")
print(f"SUPABASE_PERSISTENCE_JWT={persistence_token}\n")
print("="*80)
print("\nToken Details:")
print(f"  RAG Token:")
print(f"    Issuer: {rag_payload['iss']}")
print(f"    Reference: {rag_payload['ref']}")
print(f"    Role: {rag_payload['role']}")
print(f"    Subject: {rag_payload['sub']}")
print(f"    User Role: {rag_payload['user_role']}")
print(f"    Issued: {rag_payload['iat']}")
print(f"\n  Persistence Token:")
print(f"    Issuer: {persistence_payload['iss']}")
print(f"    Reference: {persistence_payload['ref']}")
print(f"    Role: {persistence_payload['role']}")
print(f"    Subject: {persistence_payload['sub']}")
print(f"    User Role: {persistence_payload['user_role']}")
print(f"    Issued: {persistence_payload['iat']}")
print("="*80)
