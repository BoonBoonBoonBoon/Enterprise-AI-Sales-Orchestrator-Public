# Security Model

This document describes the security architecture of the Agentic System.

## Overview

Security is implemented in layers:

```
┌─────────────────────────────────────────────────┐
│              Application Layer                  │
│         (Input validation, sanitization)        │
├─────────────────────────────────────────────────┤
│               API Gateway                       │
│         (Supabase anon_key + JWT)              │
├─────────────────────────────────────────────────┤
│              Database Layer                     │
│         (PostgreSQL GRANT + RLS)               │
├─────────────────────────────────────────────────┤
│               Network Layer                     │
│         (TLS, VPC, Firewall)                   │
└─────────────────────────────────────────────────┘
```

---

## Authentication

### 3-Layer Authentication Stack

Every database request passes through three authentication layers:

#### Layer 1: API Gateway

```http
POST https://your-project.supabase.co/rest/v1/leads
apikey: <anon_key>
Authorization: Bearer <signed_jwt>
```

#### Layer 2: PostgreSQL GRANT

```sql
-- Role can only perform granted operations
GRANT SELECT ON leads TO agent_reader;
GRANT SELECT, INSERT, UPDATE, DELETE ON leads TO agent_writer;
```

#### Layer 3: Row-Level Security

```sql
CREATE POLICY "tenant_isolation" ON leads
FOR ALL
USING (
    tenant_id = current_setting('request.jwt.claims')::json->>'tenant_id'
);
```

### JWT Structure

```json
{
  "role": "agent_writer",
  "tenant_id": "agentic-dev",
  "iat": 1705320000,
  "exp": 1705406400
}
```

---

## Authorization

### Database Roles

| Role           | Permissions                    | Used By                   |
| -------------- | ------------------------------ | ------------------------- |
| `anon`         | None (blocked by RLS)          | Not used                  |
| `agent_reader` | SELECT only                    | RAG Agent                 |
| `agent_writer` | SELECT, INSERT, UPDATE, DELETE | Persistence Agent         |
| `service_role` | Full admin                     | Migrations, admin scripts |

### Role Assignment

```python
from services.persistence.supabase_adapter import SupabaseAdapter

# RAG Agent uses reader role
rag_adapter = SupabaseAdapter(role="agent_reader")

# Persistence Agent uses writer role
persist_adapter = SupabaseAdapter(role="agent_writer")
```

---

## Multi-Tenancy

### Tenant Isolation

All data is isolated by tenant through:

1. **Stream Prefixes**: `{tenant_id}:agents:rag:tasks`
2. **Database RLS**: Filters by `tenant_id` JWT claim
3. **Environment Config**: `TENANT_ID` per deployment

### RLS Policy

```sql
CREATE POLICY "tenant_isolation" ON leads
FOR ALL
USING (
    client_id IN (
        SELECT id FROM clients
        WHERE tenant_id = current_setting('request.jwt.claims')::json->>'tenant_id'
    )
);
```

---

## Secrets Management

### Secret Types

| Secret                | Storage                   | Access          |
| --------------------- | ------------------------- | --------------- |
| `SUPABASE_URL`        | Env var / Secrets Manager | All agents      |
| `SUPABASE_ANON_KEY`   | Env var / Secrets Manager | All agents      |
| `SUPABASE_JWT_SECRET` | Env var / Secrets Manager | JWT signing     |
| `OPENAI_API_KEY`      | Env var / Secrets Manager | Copywriter only |
| `GMAIL_REFRESH_TOKEN` | Env var / Secrets Manager | Email service   |

### Best Practices

- Never log secrets
- Rotate secrets regularly
- Use different secrets per environment
- Store in secrets manager for production

---

## Input Validation

### Task Payload Validation

```python
from pydantic import BaseModel, EmailStr

class LeadCreate(BaseModel):
    name: str
    email: EmailStr
    client_id: UUID

    class Config:
        extra = "forbid"  # Reject unknown fields

# In agent
def process_task(self, task: dict):
    payload = LeadCreate(**task["payload"])  # Validates
    # Continue with validated data
```

### SQL Injection Prevention

```python
# ❌ NEVER
query = f"SELECT * FROM leads WHERE email = '{email}'"

# ✅ ALWAYS use parameterized queries
adapter.query("leads", {"email": email})
```

---

## Network Security

### Production Setup

```
┌─────────────────────────────────────────────────────────────┐
│                         VPC                                 │
│                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────────────────┐  │
│  │ Internet │───▶│   ALB    │───▶│   Private Subnet     │  │
│  │          │    │ (HTTPS)  │    │                      │  │
│  └──────────┘    └──────────┘    │  ┌────────────────┐  │  │
│                                   │  │    Agents      │  │  │
│                                   │  └────────────────┘  │  │
│                                   │                      │  │
│                                   │  ┌────────────────┐  │  │
│                                   │  │     Redis      │  │  │
│                                   │  └────────────────┘  │  │
│                                   │                      │  │
│                                   └──────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                        │
                        ▼ (TLS)
              ┌──────────────────┐
              │    Supabase      │
              │  (Managed Cloud) │
              └──────────────────┘
```

### TLS Configuration

```python
# Redis with TLS
redis_client = redis.from_url(
    "rediss://redis-host:6379/0",  # Note: rediss:// for TLS
    ssl_cert_reqs="required"
)
```

---

## Audit Logging

### What's Logged

- All Manager decisions
- All database writes
- All external API calls
- Authentication failures

### Log Format

```json
{
  "timestamp": "2025-01-15T10:00:00Z",
  "level": "INFO",
  "component": "persistence_agent",
  "tenant_id": "agentic-dev",
  "action": "create",
  "table": "leads",
  "record_id": "uuid",
  "user_role": "agent_writer"
}
```

### Sensitive Data

```python
# ❌ NEVER log sensitive data
logger.info(f"API key: {api_key}")

# ✅ Log references only
logger.info(f"Using API key ending in: ...{api_key[-4:]}")
```

---

## Threat Model

### Threats & Mitigations

| Threat              | Mitigation                              |
| ------------------- | --------------------------------------- |
| SQL Injection       | Parameterized queries, input validation |
| Cross-tenant access | RLS policies with tenant_id             |
| Credential theft    | Secrets manager, rotation               |
| Man-in-the-middle   | TLS everywhere                          |
| Unauthorized access | JWT auth, role-based access             |
| Data exfiltration   | Audit logging, least privilege          |

---

## Security Checklist

### Development

- [ ] Secrets in `.env` (not committed)
- [ ] Input validation on all endpoints
- [ ] No secrets in logs
- [ ] Dependencies scanned for vulnerabilities

### Staging/Production

- [ ] Secrets in Secrets Manager
- [ ] TLS enabled for all connections
- [ ] RLS policies verified
- [ ] Audit logging enabled
- [ ] Network isolation configured
- [ ] Regular secret rotation

## Related

- [Row-Level Security](../reference/database/rls.md)
- [Secrets Management](../guides/deploy/secrets.md)
- [Multi-Tenancy Concept](../concepts/multi-tenancy.md)
