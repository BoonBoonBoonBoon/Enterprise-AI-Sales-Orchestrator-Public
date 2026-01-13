# Row-Level Security (RLS)

The Agentic System uses Supabase Row-Level Security to enforce fine-grained access control at the database level.

## Overview

RLS is the third layer in our 3-layer authentication stack:

```
┌────────────────────────────────────────────────────────┐
│ Layer 1: API Gateway                                   │
│   • Supabase anon_key                                  │
│   • Custom JWT in Authorization header                 │
└────────────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────┐
│ Layer 2: PostgreSQL GRANT                              │
│   • Role-based permissions (agent_reader, agent_writer)│
│   • Controls table-level access                        │
└────────────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────┐
│ Layer 3: RLS Policies                                  │
│   • Row-level filtering                                │
│   • JWT claims inspection                              │
│   • Enforced per-query                                 │
└────────────────────────────────────────────────────────┘
```

## Database Roles

### agent_reader

Read-only access for RAG Agent:

```sql
CREATE ROLE agent_reader;

-- Grant SELECT on all relevant tables
GRANT SELECT ON leads TO agent_reader;
GRANT SELECT ON staging_leads TO agent_reader;
GRANT SELECT ON conversations TO agent_reader;
GRANT SELECT ON messages TO agent_reader;
GRANT SELECT ON clients TO agent_reader;
GRANT SELECT ON campaigns TO agent_reader;
```

### agent_writer

Full CRUD access for Persistence Agent:

```sql
CREATE ROLE agent_writer;

-- Grant all operations
GRANT SELECT, INSERT, UPDATE, DELETE ON leads TO agent_writer;
GRANT SELECT, INSERT, UPDATE, DELETE ON staging_leads TO agent_writer;
GRANT SELECT, INSERT, UPDATE, DELETE ON conversations TO agent_writer;
GRANT SELECT, INSERT, UPDATE, DELETE ON messages TO agent_writer;
GRANT SELECT, INSERT, UPDATE, DELETE ON staging_conversations TO agent_writer;
GRANT SELECT, INSERT, UPDATE, DELETE ON staging_messages TO agent_writer;

-- Allow sequence usage for ID generation
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO agent_writer;
```

## RLS Policies

### Enabling RLS

```sql
-- Enable RLS on all tables
ALTER TABLE clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
```

### Policy Structure

```sql
CREATE POLICY policy_name ON table_name
    FOR operation  -- SELECT, INSERT, UPDATE, DELETE, or ALL
    TO role_name
    USING (condition)  -- Filter rows (read operations)
    WITH CHECK (condition);  -- Validate rows (write operations)
```

### Role-Based Policies

```sql
-- Agent reader can SELECT all rows
CREATE POLICY agent_reader_select ON leads
    FOR SELECT
    TO agent_reader
    USING (true);

-- Agent writer can do everything
CREATE POLICY agent_writer_all ON leads
    FOR ALL
    TO agent_writer
    USING (true)
    WITH CHECK (true);
```

### JWT Claim Inspection

Access JWT claims in policies:

```sql
-- Example: Restrict to tenant
CREATE POLICY tenant_isolation ON leads
    FOR ALL
    USING (
        client_id::text = current_setting('request.jwt.claims', true)::json->>'client_id'
    );
```

## JWT Authentication

### Custom JWT Structure

```json
{
  "role": "agent_writer",
  "client_id": "uuid-client",
  "tenant_id": "agentic-dev",
  "exp": 1705234567
}
```

### Generating JWTs

```python
import jwt
from datetime import datetime, timedelta

def create_agent_jwt(role: str, client_id: str = None) -> str:
    payload = {
        "role": role,  # "agent_reader" or "agent_writer"
        "client_id": client_id,
        "exp": datetime.utcnow() + timedelta(hours=1)
    }

    return jwt.encode(
        payload,
        os.environ["SUPABASE_JWT_SECRET"],
        algorithm="HS256"
    )
```

### Using with Supabase

```python
from supabase import create_client

def get_supabase_client(role: str):
    # Create custom JWT
    token = create_agent_jwt(role)

    # Initialize client with anon key
    client = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_ANON_KEY"]
    )

    # Set custom JWT in Authorization header
    client.postgrest.auth(token)

    return client
```

## SupabaseAdapter

Our adapter handles role management:

```python
from services.persistence.supabase_adapter import SupabaseAdapter

# Reader role (RAG Agent)
reader = SupabaseAdapter(role="agent_reader")
leads = reader.query("leads", {"status": "qualified"})

# Writer role (Persistence Agent)
writer = SupabaseAdapter(role="agent_writer")
writer.write("leads", {"name": "John", "email": "john@example.com"})
```

### Adapter Implementation

```python
class SupabaseAdapter:
    def __init__(self, role: str = "agent_reader"):
        self.role = role
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = self._create_client()
        return self._client

    def _create_client(self):
        client = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_ANON_KEY"]
        )

        # Apply role via JWT
        token = self._create_role_jwt()
        client.postgrest.auth(token)

        return client
```

## Debugging RLS

### Check Current Role

```sql
SELECT current_user, current_setting('request.jwt.claims', true);
```

### Test Policy

```sql
-- Set role for testing
SET ROLE agent_reader;

-- Try operation
SELECT * FROM leads;  -- Should work
INSERT INTO leads (...) VALUES (...);  -- Should fail

-- Reset
RESET ROLE;
```

### View Policies

```sql
SELECT * FROM pg_policies WHERE tablename = 'leads';
```

## Common Issues

### RLS Denied Error

```
Error: new row violates row-level security policy
```

**Causes:**

- Wrong role used
- JWT expired
- Policy condition not met

**Fix:**

```python
# Verify role
adapter = SupabaseAdapter(role="agent_writer")  # Not agent_reader

# Check JWT expiration
token = create_agent_jwt(role, expiry_hours=24)  # Longer expiry
```

### Policy Not Applied

```
# All rows visible when should be filtered
```

**Causes:**

- RLS not enabled on table
- Using service_role key (bypasses RLS)

**Fix:**

```sql
ALTER TABLE leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE leads FORCE ROW LEVEL SECURITY;  -- Force for table owner too
```

## Best Practices

1. **Always enable RLS** — On all tables with sensitive data
2. **Use least privilege** — agent_reader for reads, agent_writer only when needed
3. **Short JWT expiry** — 1 hour max for agent operations
4. **Never expose service_role** — Bypasses all RLS
5. **Test policies** — Verify access before deployment
6. **Log denials** — Monitor for access issues

## Related

- [ADR-004: Supabase RLS](../../architecture/decisions/004-supabase-rls-3-layer-auth.md)
- [Database Schema](schema.md)
- [Environment Variables](../config/env-vars.md)
- [Persistence Agent](../../components/tier-3/persistence.md)
