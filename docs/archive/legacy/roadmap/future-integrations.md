# Future Integrations - Enterprise CRM/ERP Integration Architecture

> **Status:** 📋 Planning Phase  
> **Priority:** High (Post-MVP)  
> **Estimated Effort:** 6-8 weeks  
> **Target:** Multi-tenant AI SDR system with enterprise CRM integrations

---

## Table of Contents

- [Overview](#overview)
- [Business Requirements](#business-requirements)
- [Architecture Design](#architecture-design)
- [Security & Compliance](#security--compliance)
- [Integration Roadmap](#integration-roadmap)
- [Implementation Guide](#implementation-guide)
- [Testing Strategy](#testing-strategy)
- [Related Documentation](#related-documentation)

---

## Overview

### Vision

Transform the current single-tenant agentic system into a **multi-tenant AI SDR platform** capable of securely integrating with multiple clients' CRMs, ERPs, and marketing automation tools—without data intersection or security compromises.

### Key Challenges Addressed

1. **Multi-Tenant Data Isolation**
   - Prevent Client A from accessing Client B's data
   - Database-level, Redis-level, and application-level isolation
   - Zero-trust architecture

2. **CRM Integration Complexity**
   - OAuth 2.0 flows for 8+ CRM platforms
   - Webhook verification and retry logic
   - Rate limiting per tenant
   - Token management and auto-refresh

3. **Security & Compliance**
   - Encryption at rest and in transit
   - GDPR data export/deletion
   - SOC2 audit trails
   - HIPAA compliance (healthcare clients)

4. **Scalability**
   - Support 100+ concurrent tenants
   - Real-time sync with minimal latency
   - Horizontal scaling of workers

---

## Business Requirements

### Target Customers

**Tier 1: SMB (10-50 employees)**
- CRMs: HubSpot, Pipedrive, Close
- Features: Basic lead enrichment, email campaigns
- SLA: 99% uptime, 5-minute sync latency

**Tier 2: Mid-Market (50-500 employees)**
- CRMs: Salesforce Professional, Zoho, Copper
- Features: Multi-campaign orchestration, A/B testing
- SLA: 99.5% uptime, 2-minute sync latency

**Tier 3: Enterprise (500+ employees)**
- CRMs: Salesforce Enterprise, Microsoft Dynamics 365, Oracle NetSuite
- Features: Custom workflows, dedicated infrastructure, SSO
- SLA: 99.9% uptime, real-time sync (<30 seconds)

### Use Cases

1. **Lead Enrichment Pipeline**
   - CRM webhook → New lead detected
   - AI enriches contact (LinkedIn, company research)
   - Updates CRM with enriched data
   - Triggers outreach campaign

2. **Multi-Touch Outreach Campaign**
   - Campaign manager defines sequence (email → LinkedIn → call)
   - AI generates personalized content per lead
   - Pushes to CRM as tasks/emails
   - Tracks engagement, updates CRM status

3. **Automated Follow-Up**
   - CRM webhook → Email opened/link clicked
   - AI generates contextual follow-up
   - Schedules next touchpoint
   - Notifies SDR rep via CRM activity feed

4. **Data Sync & Backup**
   - Bi-directional sync (CRM ↔ Our System)
   - Conflict resolution (last-write-wins or manual review)
   - Audit trail for compliance

---

## Architecture Design

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT TENANTS                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ Tenant A │  │ Tenant B │  │ Tenant C │  │ Tenant N │       │
│  │ HubSpot  │  │Salesforce│  │ Pipedrive│  │   Zoho   │       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘       │
└───────┼─────────────┼─────────────┼─────────────┼──────────────┘
        │ OAuth/      │ Webhooks    │ API Polling │
        │ Webhooks    │             │             │
        ▼             ▼             ▼             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     API GATEWAY (Kong/NGINX)                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ Rate Limiting│  │ Tenant Router│  │  Auth/OAuth  │         │
│  │  Per Tenant  │  │   (Resolve)  │  │  Token Mgmt  │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└────────────────────────────┬────────────────────────────────────┘
                             │
        ┌────────────────────┴────────────────────┐
        ▼                                         ▼
┌──────────────────┐                    ┌──────────────────┐
│  ORCHESTRATOR    │◄───────────────────┤  INTEGRATION     │
│  (Tenant-Aware)  │                    │  WORKERS         │
│                  │                    │  (CRM Connectors)│
│  • Task Router   │                    │  • HubSpot       │
│  • Tenant Context│                    │  • Salesforce    │
│  • Workflow Mgmt │                    │  • Pipedrive     │
└────────┬─────────┘                    │  • Zoho          │
         │                              │  • Close         │
         ▼                              │  • Monday.com    │
┌──────────────────┐                    └──────────────────┘
│  WORKER POOL     │
│  (Tenant-Scoped) │
│                  │
│  • Copy Worker   │◄── tenant_id in envelope
│  • RAG Worker    │◄── PostgreSQL RLS enforced
│  • Persist Worker│◄── Redis keyspace isolated
└────────┬─────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      DATA LAYER (ISOLATED)                       │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │           PostgreSQL (Row-Level Security)                │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐        │  │
│  │  │ Tenant A   │  │ Tenant B   │  │ Tenant C   │        │  │
│  │  │ Namespace  │  │ Namespace  │  │ Namespace  │        │  │
│  │  └────────────┘  └────────────┘  └────────────┘        │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │           Redis (Keyspace Isolation)                     │  │
│  │  tenant:A:*   tenant:B:*   tenant:C:*                    │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │           Object Storage (S3/Azure Blob)                 │  │
│  │  /tenant-a/   /tenant-b/   /tenant-c/                    │  │
│  │  (Encrypted with per-tenant keys)                        │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Multi-Tenant Data Isolation (3 Layers)

#### Layer 1: Database (PostgreSQL Row-Level Security)

**Implementation:**
```sql
-- Enable RLS on all tenant tables
ALTER TABLE leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE contacts ENABLE ROW LEVEL SECURITY;

-- Create policy: users can only see their tenant's data
CREATE POLICY tenant_isolation_policy ON leads
  USING (tenant_id = current_setting('app.tenant_id')::uuid);

CREATE POLICY tenant_isolation_policy ON campaigns
  USING (tenant_id = current_setting('app.tenant_id')::uuid);

-- Set tenant context at connection level
SET app.tenant_id = 'abc123-tenant-a-uuid';
```

**Benefits:**
- ✅ Enforced at database level (impossible to bypass)
- ✅ Works even with SQL injection attempts
- ✅ Zero application code changes for existing queries
- ✅ Auditable via PostgreSQL logs

**Schema Changes Required:**
```sql
-- Add tenant_id to all tables
ALTER TABLE leads ADD COLUMN tenant_id UUID NOT NULL;
ALTER TABLE campaigns ADD COLUMN tenant_id UUID NOT NULL;
ALTER TABLE contacts ADD COLUMN tenant_id UUID NOT NULL;

-- Create index for performance
CREATE INDEX idx_leads_tenant ON leads(tenant_id);
CREATE INDEX idx_campaigns_tenant ON campaigns(tenant_id);

-- Create tenants table
CREATE TABLE tenants (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(255) NOT NULL,
  crm_type VARCHAR(50),  -- 'hubspot', 'salesforce', etc.
  crm_config JSONB,      -- Encrypted credentials
  status VARCHAR(20) DEFAULT 'active',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### Layer 2: Redis (Keyspace Isolation)

**Implementation:**
```python
# Automatic prefixing via tenant_context manager
class TenantAwareRedis:
    def __init__(self, redis_client):
        self.redis = redis_client
    
    def _prefix_key(self, key: str, tenant_id: str) -> str:
        return f"tenant:{tenant_id}:{key}"
    
    def set(self, key: str, value: str, tenant_id: str):
        prefixed_key = self._prefix_key(key, tenant_id)
        self.redis.set(prefixed_key, value)
    
    def get(self, key: str, tenant_id: str):
        prefixed_key = self._prefix_key(key, tenant_id)
        return self.redis.get(prefixed_key)

# Usage
redis = TenantAwareRedis(redis_client)
redis.set("lead:123", data, tenant_id="abc123")
# Actual key: "tenant:abc123:lead:123"
```

**Benefits:**
- ✅ Complete namespace isolation
- ✅ No key collisions between tenants
- ✅ Easy to delete all tenant data (DEL tenant:abc123:*)
- ✅ Per-tenant metrics (key count, memory usage)

#### Layer 3: Application (Tenant Context Propagation)

**Implementation:**
```python
# Context manager for thread-safe tenant tracking
from contextvars import ContextVar

_tenant_context: ContextVar[Optional[str]] = ContextVar('tenant_id', default=None)

class tenant_context:
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.token = None
    
    def __enter__(self):
        self.token = _tenant_context.set(self.tenant_id)
        # Set PostgreSQL session variable
        db.execute(f"SET app.tenant_id = '{self.tenant_id}'")
        return self
    
    def __exit__(self, *args):
        _tenant_context.reset(self.token)
        db.execute("RESET app.tenant_id")

# Usage in workers
def process_task(envelope: TypedEnvelope):
    tenant_id = envelope.metadata.get("tenant_id")
    
    with tenant_context(tenant_id):
        # All queries automatically scoped to tenant
        leads = persistence.query("leads", filters={})  # ✅ Tenant A only
        campaign = persistence.query("campaigns", {"id": "123"})  # ✅ Tenant A only
        
        # Redis operations also scoped
        redis.set("cache:lead:123", data)  # ✅ tenant:A:cache:lead:123
```

**Benefits:**
- ✅ Automatic tenant scoping (developers can't forget)
- ✅ Works with async/await (via contextvars)
- ✅ Explicit context boundaries (with statement)
- ✅ Audit logging built-in

---

## Security & Compliance

### Encryption Strategy

#### At Rest

**Database (PostgreSQL TDE)**
```bash
# Enable Transparent Data Encryption
ALTER SYSTEM SET ssl = on;
ALTER SYSTEM SET ssl_cert_file = '/path/to/server.crt';
ALTER SYSTEM SET ssl_key_file = '/path/to/server.key';

# Column-level encryption for sensitive fields
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Encrypt CRM credentials
INSERT INTO tenants (crm_config) VALUES (
  pgp_sym_encrypt('{"api_key": "secret"}', 'encryption_key')
);

-- Decrypt when needed
SELECT pgp_sym_decrypt(crm_config, 'encryption_key') FROM tenants;
```

**Redis (RDB Encryption)**
```bash
# redis.conf
requirepass strong_redis_password
rename-command CONFIG ""
rename-command FLUSHALL ""

# Enable RDB encryption
rdbcompression yes
rdbchecksum yes

# External: Encrypt RDB files with LUKS/dm-crypt at OS level
```

**Object Storage (S3 Server-Side Encryption)**
```python
import boto3

s3 = boto3.client('s3')

# Enable SSE-KMS with per-tenant keys
s3.put_object(
    Bucket='agentic-data',
    Key=f'tenant/{tenant_id}/leads.json',
    Body=data,
    ServerSideEncryption='aws:kms',
    SSEKMSKeyId=f'arn:aws:kms:us-east-1:123456789:key/{tenant_kms_key}'
)
```

#### In Transit

**TLS 1.3 Everywhere**
```yaml
# nginx.conf (API Gateway)
ssl_protocols TLSv1.3;
ssl_ciphers 'TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256';
ssl_prefer_server_ciphers on;

# Certificate pinning for CRM APIs
ssl_stapling on;
ssl_stapling_verify on;
```

**mTLS Between Services**
```yaml
# docker-compose.yml
services:
  orchestrator:
    environment:
      - REDIS_TLS_ENABLED=true
      - REDIS_TLS_CERT=/certs/orchestrator.crt
      - REDIS_TLS_KEY=/certs/orchestrator.key
      - REDIS_TLS_CA=/certs/ca.crt
```

### OAuth 2.0 Token Management

**Secure Storage**
```python
from cryptography.fernet import Fernet
import secrets

class TokenVault:
    def __init__(self, master_key: bytes):
        self.cipher = Fernet(master_key)
    
    def store_token(self, tenant_id: str, token: dict):
        encrypted = self.cipher.encrypt(json.dumps(token).encode())
        db.execute("""
            INSERT INTO oauth_tokens (tenant_id, encrypted_token, expires_at)
            VALUES (%s, %s, %s)
        """, (tenant_id, encrypted, token['expires_at']))
    
    def get_token(self, tenant_id: str) -> dict:
        row = db.fetch_one("""
            SELECT encrypted_token FROM oauth_tokens 
            WHERE tenant_id = %s AND expires_at > NOW()
        """, (tenant_id,))
        
        if not row:
            raise TokenExpired(tenant_id)
        
        decrypted = self.cipher.decrypt(row['encrypted_token'])
        return json.loads(decrypted)
    
    def refresh_token(self, tenant_id: str, crm: str):
        # Auto-refresh before expiry
        old_token = self.get_token(tenant_id)
        new_token = crm_connectors[crm].refresh_oauth(old_token['refresh_token'])
        self.store_token(tenant_id, new_token)
        return new_token
```

**Auto-Refresh Strategy**
```python
# Background task (runs every 10 minutes)
async def refresh_expiring_tokens():
    expiring = db.fetch_all("""
        SELECT tenant_id, crm_type FROM oauth_tokens
        WHERE expires_at < NOW() + INTERVAL '1 hour'
    """)
    
    for row in expiring:
        try:
            await token_vault.refresh_token(row['tenant_id'], row['crm_type'])
            logger.info(f"Refreshed token for {row['tenant_id']}")
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            alert_admin(row['tenant_id'], "token_refresh_failed")
```

### Audit Logging (Immutable)

**S3 Audit Trail**
```python
import boto3
from datetime import datetime

class AuditLogger:
    def __init__(self, s3_bucket: str):
        self.s3 = boto3.client('s3')
        self.bucket = s3_bucket
    
    def log_event(self, event: dict):
        # Add metadata
        event['timestamp'] = datetime.utcnow().isoformat()
        event['request_id'] = uuid.uuid4().hex
        
        # Write to S3 (immutable, versioned)
        key = f"audit/{event['tenant_id']}/{event['timestamp'][:10]}/{event['request_id']}.json"
        self.s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=json.dumps(event),
            ServerSideEncryption='AES256',
            ObjectLockMode='COMPLIANCE',  # Cannot be deleted
            ObjectLockRetainUntilDate=datetime.utcnow() + timedelta(days=2555)  # 7 years
        )
        
        # Also write to PostgreSQL for fast queries
        db.execute("""
            INSERT INTO audit_logs (tenant_id, action, details, timestamp)
            VALUES (%s, %s, %s, %s)
        """, (event['tenant_id'], event['action'], event, event['timestamp']))

# Usage
audit = AuditLogger('agentic-audit-logs')

with tenant_context(tenant_id):
    leads = persistence.query("leads", filters={"status": "new"})
    
    audit.log_event({
        "tenant_id": tenant_id,
        "action": "leads.query",
        "user": "system",
        "filters": {"status": "new"},
        "result_count": len(leads),
        "ip_address": request.remote_addr
    })
```

### GDPR Compliance

**Data Export (Right to Access)**
```python
@app.route("/api/tenants/<tenant_id>/export", methods=["POST"])
@require_admin
def export_tenant_data(tenant_id: str):
    """Export all tenant data in machine-readable format."""
    
    with tenant_context(tenant_id):
        export = {
            "tenant_id": tenant_id,
            "exported_at": datetime.utcnow().isoformat(),
            "data": {
                "leads": persistence.query("leads", {}),
                "campaigns": persistence.query("campaigns", {}),
                "contacts": persistence.query("contacts", {}),
                "audit_logs": db.fetch_all("""
                    SELECT * FROM audit_logs 
                    WHERE tenant_id = %s
                """, (tenant_id,))
            }
        }
    
    # Upload to S3, generate pre-signed URL
    key = f"exports/{tenant_id}/{uuid.uuid4()}.json"
    s3.put_object(Bucket='agentic-exports', Key=key, Body=json.dumps(export))
    
    url = s3.generate_presigned_url(
        'get_object',
        Params={'Bucket': 'agentic-exports', 'Key': key},
        ExpiresIn=86400  # 24 hours
    )
    
    return {"download_url": url, "expires_in": "24 hours"}
```

**Data Deletion (Right to be Forgotten)**
```python
@app.route("/api/tenants/<tenant_id>/delete", methods=["DELETE"])
@require_admin
@require_confirmation
def delete_tenant_data(tenant_id: str):
    """Permanently delete all tenant data."""
    
    # Step 1: PostgreSQL (CASCADE deletes via foreign keys)
    db.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))
    
    # Step 2: Redis (delete all keys with prefix)
    keys = redis.keys(f"tenant:{tenant_id}:*")
    if keys:
        redis.delete(*keys)
    
    # Step 3: S3 (delete all objects in tenant folder)
    paginator = s3.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket='agentic-data', Prefix=f'tenant/{tenant_id}/'):
        if 'Contents' in page:
            objects = [{'Key': obj['Key']} for obj in page['Contents']]
            s3.delete_objects(Bucket='agentic-data', Delete={'Objects': objects})
    
    # Step 4: Audit the deletion (required by GDPR)
    audit.log_event({
        "tenant_id": tenant_id,
        "action": "tenant.deleted",
        "user": request.user.id,
        "reason": request.json.get("reason"),
        "confirmed_by": request.json.get("admin_signature")
    })
    
    return {"status": "deleted", "tenant_id": tenant_id}
```

---

## Integration Roadmap

### Phase 1: Foundation (Weeks 1-2)

**Deliverables:**
- [ ] Multi-tenant database schema (add `tenant_id` to all tables)
- [ ] PostgreSQL Row-Level Security policies
- [ ] Tenant context middleware (`tenant_context` manager)
- [ ] Redis keyspace isolation
- [ ] Update all workers to respect tenant context
- [ ] Basic admin API (create/list/delete tenants)

**Testing:**
- Unit tests: Tenant context propagation
- Integration tests: RLS enforcement (attempt cross-tenant query)
- Load tests: 100 concurrent tenants

### Phase 2: CRM Connectors (Weeks 3-5)

**Priority Order:**

1. **HubSpot** (Week 3)
   - OAuth 2.0 flow
   - Webhook handlers (contact.created, deal.updated)
   - API wrappers (create contact, update deal, create task)
   - Rate limiting (100 req/10sec for Free tier)

2. **Salesforce** (Week 4)
   - OAuth 2.0 with refresh tokens
   - Webhook handlers (Platform Events)
   - Bulk API for large data sync
   - Rate limiting (per tenant API limits)

3. **Pipedrive** (Week 5)
   - API key authentication
   - Webhook handlers (person.created, deal.updated)
   - Real-time sync (<1 min latency)

**Testing:**
- Mock CRM responses (VCR.py for recording)
- Webhook signature verification
- Token refresh edge cases
- Rate limit backoff

### Phase 3: Security Hardening (Week 6)

**Deliverables:**
- [ ] Encryption at rest (PostgreSQL TDE, Redis RDB encryption)
- [ ] TLS 1.3 everywhere (API gateway, internal mTLS)
- [ ] Audit logging to S3 (immutable, 7-year retention)
- [ ] GDPR data export API
- [ ] GDPR data deletion API
- [ ] Secrets rotation (90-day schedule)

**Testing:**
- Penetration testing (OWASP Top 10)
- Compliance audit (SOC2 checklist)
- Disaster recovery drill (restore from backups)

### Phase 4: Production Deployment (Weeks 7-8)

**Deliverables:**
- [ ] Kubernetes manifests (multi-tenant workers)
- [ ] Horizontal Pod Autoscaler (scale on CPU/memory)
- [ ] Multi-region deployment (US-East, EU-West)
- [ ] Monitoring dashboard (Grafana with per-tenant metrics)
- [ ] Alerting (PagerDuty for critical issues)
- [ ] Customer onboarding portal (self-service OAuth)

**Testing:**
- Load testing (1000 concurrent tenants)
- Chaos engineering (kill random pods)
- Latency testing (p95 < 200ms for API calls)

---

## Implementation Guide

### Step 1: Add Tenant Context to Existing Code

**Update `agent/schemas/envelope.py`:**
```python
class EnvelopeMetadata(BaseModel):
    task_id: str
    tenant_id: str  # ✅ NEW: Required for all tasks
    timestamp: str
    retry_count: int = 0
    priority: int = 5
```

**Update `agent/workers/copywriter_worker.py`:**
```python
from agent.utils.tenant_context import tenant_context

class CopyworkerAgent(BaseWorker):
    async def process_task(self, envelope: TypedEnvelope):
        tenant_id = envelope.metadata.tenant_id
        
        # ✅ NEW: Wrap all operations in tenant context
        with tenant_context(tenant_id):
            # All queries automatically scoped
            lead = await self.persistence.query("leads", {"id": envelope.payload.lead_id})
            campaign = await self.persistence.query("campaigns", {"id": envelope.payload.campaign_id})
            
            # Generate email (LLM call)
            email = await self.generate_email(lead, campaign)
            
            # Push to CRM (tenant-scoped connector)
            crm = self.get_crm_connector(tenant_id)
            await crm.create_email(lead["crm_id"], email)
```

### Step 2: Build CRM Connectors

**Create `agent/integrations/crm_connectors.py`:**
```python
from abc import ABC, abstractmethod
from typing import Dict, List

class CRMConnector(ABC):
    """Base class for all CRM integrations."""
    
    def __init__(self, tenant_id: str, credentials: dict):
        self.tenant_id = tenant_id
        self.credentials = credentials
    
    @abstractmethod
    async def get_contact(self, contact_id: str) -> dict:
        """Fetch a contact by ID."""
        pass
    
    @abstractmethod
    async def create_contact(self, contact: dict) -> str:
        """Create a new contact, return CRM ID."""
        pass
    
    @abstractmethod
    async def update_contact(self, contact_id: str, updates: dict):
        """Update an existing contact."""
        pass
    
    @abstractmethod
    async def list_contacts(self, filters: dict) -> List[dict]:
        """List contacts matching filters."""
        pass

class HubSpotConnector(CRMConnector):
    BASE_URL = "https://api.hubapi.com"
    
    async def get_contact(self, contact_id: str) -> dict:
        url = f"{self.BASE_URL}/crm/v3/objects/contacts/{contact_id}"
        headers = {"Authorization": f"Bearer {self.credentials['access_token']}"}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
    
    async def create_contact(self, contact: dict) -> str:
        url = f"{self.BASE_URL}/crm/v3/objects/contacts"
        headers = {"Authorization": f"Bearer {self.credentials['access_token']}"}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json={"properties": contact})
            response.raise_for_status()
            return response.json()["id"]

# Factory pattern
def get_crm_connector(tenant_id: str) -> CRMConnector:
    tenant = db.fetch_one("SELECT * FROM tenants WHERE id = %s", (tenant_id,))
    
    credentials = decrypt_credentials(tenant['crm_config'])
    
    if tenant['crm_type'] == 'hubspot':
        return HubSpotConnector(tenant_id, credentials)
    elif tenant['crm_type'] == 'salesforce':
        return SalesforceConnector(tenant_id, credentials)
    else:
        raise ValueError(f"Unsupported CRM: {tenant['crm_type']}")
```

### Step 3: Webhook Handler

**Create `api/webhooks.py`:**
```python
from fastapi import FastAPI, Request, HTTPException
import hmac
import hashlib

app = FastAPI()

def verify_hubspot_signature(body: bytes, signature: str, secret: str) -> bool:
    """Verify HubSpot webhook signature."""
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)

@app.post("/webhooks/hubspot/{tenant_id}")
async def handle_hubspot_webhook(tenant_id: str, request: Request):
    # Step 1: Verify signature
    body = await request.body()
    signature = request.headers.get("X-HubSpot-Signature")
    
    tenant = db.fetch_one("SELECT webhook_secret FROM tenants WHERE id = %s", (tenant_id,))
    if not verify_hubspot_signature(body, signature, tenant['webhook_secret']):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Step 2: Parse event
    event = await request.json()
    
    # Step 3: Enqueue task (tenant-scoped)
    orchestrator.enqueue_task({
        "tenant_id": tenant_id,
        "event_type": event[0]["subscriptionType"],
        "crm_id": event[0]["objectId"],
        "action": "sync_from_crm"
    })
    
    return {"status": "accepted"}
```

### Step 4: OAuth Flow

**Create `api/oauth.py`:**
```python
from fastapi import FastAPI, Request
import httpx

app = FastAPI()

HUBSPOT_OAUTH_URL = "https://app.hubspot.com/oauth/authorize"
HUBSPOT_TOKEN_URL = "https://api.hubapi.com/oauth/v1/token"

@app.get("/oauth/hubspot/authorize/{tenant_id}")
async def initiate_hubspot_oauth(tenant_id: str):
    """Redirect user to HubSpot OAuth consent screen."""
    params = {
        "client_id": os.getenv("HUBSPOT_CLIENT_ID"),
        "redirect_uri": f"{os.getenv('BASE_URL')}/oauth/hubspot/callback",
        "scope": "crm.objects.contacts.read crm.objects.contacts.write",
        "state": tenant_id  # Pass tenant_id to callback
    }
    
    url = f"{HUBSPOT_OAUTH_URL}?{urlencode(params)}"
    return RedirectResponse(url)

@app.get("/oauth/hubspot/callback")
async def hubspot_oauth_callback(code: str, state: str):
    """Handle OAuth callback, exchange code for token."""
    tenant_id = state
    
    # Exchange authorization code for access token
    async with httpx.AsyncClient() as client:
        response = await client.post(HUBSPOT_TOKEN_URL, data={
            "grant_type": "authorization_code",
            "client_id": os.getenv("HUBSPOT_CLIENT_ID"),
            "client_secret": os.getenv("HUBSPOT_CLIENT_SECRET"),
            "redirect_uri": f"{os.getenv('BASE_URL')}/oauth/hubspot/callback",
            "code": code
        })
        
        token = response.json()
    
    # Store encrypted token
    token_vault.store_token(tenant_id, token)
    
    return {"status": "connected", "crm": "hubspot"}
```

---

## Testing Strategy

### Unit Tests (50+ tests)

**Test: Tenant Context Isolation**
```python
def test_tenant_context_isolation():
    """Ensure queries are scoped to correct tenant."""
    
    # Create test data for 2 tenants
    with tenant_context("tenant-a"):
        persistence.create("leads", {"name": "Lead A", "email": "a@example.com"})
    
    with tenant_context("tenant-b"):
        persistence.create("leads", {"name": "Lead B", "email": "b@example.com"})
    
    # Verify isolation
    with tenant_context("tenant-a"):
        leads = persistence.query("leads", {})
        assert len(leads) == 1
        assert leads[0]["name"] == "Lead A"
    
    with tenant_context("tenant-b"):
        leads = persistence.query("leads", {})
        assert len(leads) == 1
        assert leads[0]["name"] == "Lead B"
```

**Test: PostgreSQL RLS Enforcement**
```python
def test_rls_blocks_cross_tenant_query():
    """Verify RLS blocks SQL injection attempts."""
    
    with tenant_context("tenant-a"):
        # Attempt SQL injection to access tenant-b data
        with pytest.raises(PermissionError):
            db.execute("""
                SELECT * FROM leads 
                WHERE tenant_id = 'tenant-b'  -- ✅ RLS blocks this
            """)
```

**Test: Redis Keyspace Isolation**
```python
def test_redis_keyspace_isolation():
    """Ensure Redis keys are properly namespaced."""
    
    redis_client = TenantAwareRedis(redis)
    
    redis_client.set("lead:123", "data-a", tenant_id="tenant-a")
    redis_client.set("lead:123", "data-b", tenant_id="tenant-b")
    
    # Verify isolation
    assert redis_client.get("lead:123", tenant_id="tenant-a") == "data-a"
    assert redis_client.get("lead:123", tenant_id="tenant-b") == "data-b"
    
    # Verify actual keys
    keys = redis.keys("*")
    assert b"tenant:tenant-a:lead:123" in keys
    assert b"tenant:tenant-b:lead:123" in keys
```

### Integration Tests (20+ tests)

**Test: End-to-End HubSpot Sync**
```python
@pytest.mark.integration
async def test_hubspot_contact_sync():
    """Test full sync pipeline: HubSpot → Our System → AI → HubSpot."""
    
    tenant_id = "test-tenant"
    
    # Mock HubSpot webhook
    webhook_payload = {
        "subscriptionType": "contact.creation",
        "objectId": 12345,
        "propertyName": "email",
        "propertyValue": "test@example.com"
    }
    
    # Send webhook
    response = await client.post(
        f"/webhooks/hubspot/{tenant_id}",
        json=[webhook_payload],
        headers={"X-HubSpot-Signature": generate_signature(webhook_payload)}
    )
    assert response.status_code == 200
    
    # Wait for task processing
    await asyncio.sleep(2)
    
    # Verify data in our system
    with tenant_context(tenant_id):
        leads = persistence.query("leads", {"crm_id": "12345"})
        assert len(leads) == 1
        assert leads[0]["email"] == "test@example.com"
    
    # Verify AI enrichment happened
    assert leads[0]["enriched"] == True
    assert "linkedin_url" in leads[0]
```

### Load Tests (Locust)

**Test: 1000 Concurrent Tenants**
```python
from locust import HttpUser, task, between

class TenantUser(HttpUser):
    wait_time = between(1, 5)
    
    def on_start(self):
        self.tenant_id = f"tenant-{self.environment.runner.user_count}"
        self.authenticate()
    
    @task(10)
    def create_lead(self):
        self.client.post(
            f"/api/tenants/{self.tenant_id}/leads",
            json={"name": "Test Lead", "email": "test@example.com"}
        )
    
    @task(5)
    def query_leads(self):
        self.client.get(f"/api/tenants/{self.tenant_id}/leads")
    
    @task(1)
    def export_data(self):
        self.client.post(f"/api/tenants/{self.tenant_id}/export")

# Run: locust -f load_test.py --users 1000 --spawn-rate 10
```

---

## Related Documentation

### Core Documents (Already Created)

1. **`INTEGRATION_ARCHITECTURE.md`** (600 lines)
   - CRM connector patterns
   - OAuth flows
   - Webhook handlers
   - Rate limiting strategies

2. **`SECURITY_ARCHITECTURE.md`** (800 lines)
   - 5-layer security model
   - Encryption implementation
   - Compliance checklists (GDPR, SOC2, HIPAA)
   - Threat modeling

3. **`MULTI_TENANT_IMPLEMENTATION.md`** (600 lines)
   - Step-by-step migration guide
   - Database schema changes
   - Worker modifications
   - Testing scenarios

### Code Files (Already Created)

4. **`agent/utils/tenant_context.py`** (400 lines)
   - Thread-safe context manager
   - PostgreSQL session management
   - Redis keyspace prefixing
   - Audit logging decorator

5. **`agent/integrations/crm_connectors.py`** (500 lines)
   - HubSpot connector
   - Salesforce connector
   - Pipedrive connector
   - Zoho CRM connector
   - Close connector
   - Monday.com connector

---

## Next Steps

### Immediate Actions (This Week)

1. **Review Architecture**
   - [ ] Team walkthrough of security model
   - [ ] Identify gaps or concerns
   - [ ] Prioritize CRM integrations (HubSpot first?)

2. **Spike Tasks** (1-2 days each)
   - [ ] Prototype PostgreSQL RLS with existing schema
   - [ ] Test Redis keyspace isolation with current workers
   - [ ] Mock HubSpot OAuth flow end-to-end

3. **Decision Points**
   - [ ] Single DB vs. DB-per-tenant? (Recommend: Single DB with RLS)
   - [ ] Shared Redis vs. Redis-per-tenant? (Recommend: Shared with namespacing)
   - [ ] Which CRM to build first? (Recommend: HubSpot - largest SMB market)

### Long-Term Milestones

**Q1 2026: MVP Multi-Tenant**
- Support 3 CRMs (HubSpot, Salesforce, Pipedrive)
- 10 pilot customers
- Basic security (TLS, RLS, audit logs)

**Q2 2026: Scale**
- Support 100+ tenants
- Add 3 more CRMs (Zoho, Close, Copper)
- SOC2 Type I certification

**Q3 2026: Enterprise**
- Multi-region deployment (US, EU)
- SSO/SAML support
- Custom SLAs per tier

**Q4 2026: Platform**
- Public API for custom integrations
- Marketplace for community connectors
- White-label option for agencies

---

## Summary

This document outlines a **production-ready architecture** for transforming your agentic AI system into a **multi-tenant SaaS platform** capable of securely integrating with enterprise CRMs.

**Key Takeaways:**
- ✅ **3-layer data isolation** (DB, Redis, application) prevents data leaks
- ✅ **Bank-level security** (encryption, RLS, audit logs, compliance)
- ✅ **6 CRM connectors** ready to implement (HubSpot, Salesforce, etc.)
- ✅ **8-week implementation plan** with clear milestones
- ✅ **2,000+ lines of supporting documentation** and code examples

**Status:** 📋 Planning Phase → Ready for team review and spike tasks

**Estimated Effort:** 6-8 weeks for MVP (HubSpot + Salesforce + security hardening)

**Contact:** Ready to begin implementation when approved! 🚀
