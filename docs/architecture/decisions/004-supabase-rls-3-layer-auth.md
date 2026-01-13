# ADR-004: Supabase RLS 3-Layer Authentication

**Status:** ✅ Accepted  
**Date:** November 2025

## Context

We needed a database security model that provides:

1. **Role-based access** — Different agents have different permissions
2. **Tenant isolation** — Tenants cannot access each other's data
3. **Defense in depth** — Multiple security layers
4. **Auditability** — Clear understanding of who can access what

Single-layer security (just application checks) is fragile. Database-level enforcement provides stronger guarantees.

## Decision

We implement a **3-layer authentication stack**:

```
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 1: API Gateway                                           │
│  - Supabase anon_key validates request                         │
│  - Custom JWT in Authorization header                          │
│  - JWT contains: role, tenant_id                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 2: PostgreSQL GRANT                                      │
│  - Database roles: agent_reader, agent_writer                  │
│  - GRANT SELECT ON tables TO agent_reader                      │
│  - GRANT ALL ON tables TO agent_writer                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 3: Row-Level Security (RLS)                             │
│  - Policies check JWT claims                                    │
│  - current_setting('request.jwt.claims')::json->>'tenant_id'   │
│  - Row filtered to current tenant only                         │
└─────────────────────────────────────────────────────────────────┘
```

### Database Roles

| Role           | Permissions                            | Used By           |
| -------------- | -------------------------------------- | ----------------- |
| `agent_reader` | `SELECT` only                          | RAG Agent         |
| `agent_writer` | `SELECT`, `INSERT`, `UPDATE`, `DELETE` | Persistence Agent |

### JWT Structure

```json
{
  "role": "agent_writer",
  "tenant_id": "agentic-dev",
  "iat": 1704067200,
  "exp": 1704153600
}
```

### RLS Policy Example

```sql
CREATE POLICY tenant_isolation ON leads
  FOR ALL
  USING (
    tenant_id = (current_setting('request.jwt.claims')::json->>'tenant_id')
  );
```

## Consequences

### Positive

- **Defense in depth** — Compromise of one layer doesn't expose all data
- **Principle of least privilege** — Agents only get permissions they need
- **Tenant isolation guaranteed** — Database enforces, not just application
- **Auditable** — Clear role definitions in database
- **Compliance-friendly** — Meets enterprise security requirements

### Negative

- **Complexity** — Three layers to configure and maintain
- **JWT management** — Must rotate secrets, handle expiration
- **Performance** — RLS adds query overhead (minimal with proper indexes)
- **Debugging** — Harder to debug permission issues across layers

### Neutral

- **Supabase-specific** — Tied to Supabase patterns (acceptable tradeoff)
- **Migration effort** — Requires careful schema migration

## Alternatives Considered

### Option A: Application-Only Security

All permission checks in Python code.

- **Pros:** Simple, flexible, easy to change
- **Cons:** Easy to bypass, no database-level guarantees, audit harder
- **Why rejected:** Too fragile, doesn't meet security requirements

### Option B: PostgreSQL GRANT Only

Database roles without RLS.

- **Pros:** Simpler than RLS, native PostgreSQL
- **Cons:** No tenant isolation at database level, roles per table not per row
- **Why rejected:** Doesn't provide tenant isolation

### Option C: Separate Databases per Tenant

Physical isolation with one database per tenant.

- **Pros:** Strongest isolation, simple queries
- **Cons:** Expensive, connection overhead, migration complexity
- **Why rejected:** Doesn't scale for many tenants, operational burden

## Implementation

### SupabaseAdapter Usage

```python
from services.persistence.supabase_adapter import SupabaseAdapter

# Initialize with role (generates appropriate JWT)
adapter = SupabaseAdapter(role="agent_writer")

# All operations are scoped to tenant
adapter.write("leads", {"name": "John", "tenant_id": "agentic-dev"})
adapter.read("leads", "uuid-here")  # RLS filters to tenant
```

### Environment Variables

```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_JWT_SECRET=your-jwt-secret  # For signing custom JWTs
```

## References

- [Supabase Row Level Security](https://supabase.com/docs/guides/auth/row-level-security)
- [PostgreSQL GRANT](https://www.postgresql.org/docs/current/sql-grant.html)
