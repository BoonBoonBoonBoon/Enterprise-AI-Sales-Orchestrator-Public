# Database Migrations

This reference covers database schema migrations for the Agentic System.

## Overview

Migrations are managed through Supabase CLI. All migration files live in `supabase/migrations/`.

## Prerequisites

- Supabase CLI installed
- Local Supabase running (`supabase start`)
- Access to remote project (for production)

## Quick Reference

```powershell
# Create new migration
supabase migration new add_field_to_leads

# Apply migrations locally
supabase db reset

# Push to remote
supabase db push

# Pull remote changes
supabase db pull
```

## Security migrations (Jan 2026)

These migrations implement production-grade tenant isolation + invitations:

- `supabase/migrations/20260128120000_invitations_audit.sql`
  - `pending_invitations` table
  - `accept_invitation()` function
  - audit_log column extensions + indexes
- `supabase/migrations/20260128130000_complete_tenant_isolation.sql`
  - RLS enablement + policies for remaining tenant tables
  - helper lookup functions for nested tables (messages/staging/agent subtasks)
  - creates `mailboxes` and `drafts` tables (if missing) with RLS

## Tenant provisioning + portal profile (Feb 2026)

These migrations support tenant-aware portal signup + profile persistence and harden RLS to avoid recursion:

- `supabase/migrations/20260203090000_clients_profile_and_rls.sql`
  - Expands `clients` fields for portal usage
  - Adds/ensures `user_client_memberships`
  - Introduces tenant resolver `public.get_current_client_id()` (later hardened)
  - Tenant-aware RLS policy for `clients`
- `supabase/migrations/20260203100000_user_client_memberships_rls.sql`
  - RLS enablement/policies for membership table
- `supabase/migrations/20260203103000_auth_user_provisioning.sql`
  - Auth trigger wiring for provisioning (signup lifecycle)
- `supabase/migrations/20260203110000_fix_signup_rls.sql`
  - Signup-related RLS adjustments to allow provisioning to complete cleanly
- `supabase/migrations/20260203120000_user_profiles_and_signup_sync.sql`
  - Adds `public.user_profiles`
  - Adds `upsert_user_profile_from_auth()` trigger function
  - Adds `create_client_on_signup()` tenant provisioning function
- `supabase/migrations/20260203121000_accept_invitation_sets_client_id.sql`
  - Ensures invitation acceptance sets/propagates `client_id` consistently
- `supabase/migrations/20260203123000_fix_auth_signup_trigger.sql`
  - Fixes provisioning trigger behavior during auth user insert
- `supabase/migrations/20260203130000_force_auth_signup_trigger_after.sql`
  - Forces the auth provisioning trigger to be `AFTER INSERT` (prevents FK timing issues)
- `supabase/migrations/20260203133000_fix_user_client_memberships_policy.sql`
  - Adds `public.is_client_admin()` SECURITY DEFINER helper
  - Rewrites membership admin policy to avoid recursive RLS
- `supabase/migrations/20260203140000_tenant_resolution_and_client_defaults.sql`
  - Adds `public.get_client_id_for_user()` SECURITY DEFINER helper
  - Hardens `public.get_current_client_id()` to avoid recursion
  - Adds insert-default trigger `set_client_id_from_current()` for `mailboxes` and `drafts`

---

## When migrations get “stuck” (remote history mismatch)

If Supabase CLI reports that a remote migration version exists but the local file is missing or renamed, repair history
and re-run:

```powershell
supabase migration list

# Mark the problematic version as reverted (example version)
supabase migration repair --status reverted 20260128

# Then push again
supabase db push --include-all
```

## Migration Workflow

### 1. Create Migration

```powershell
supabase migration new add_priority_to_leads
# Creates: supabase/migrations/20250115120000_add_priority_to_leads.sql
```

### 2. Write SQL

```sql
-- supabase/migrations/20250115120000_add_priority_to_leads.sql

-- Add column
ALTER TABLE leads
ADD COLUMN priority TEXT DEFAULT 'normal'
CHECK (priority IN ('low', 'normal', 'high', 'urgent'));

-- Create index
CREATE INDEX idx_leads_priority ON leads(priority);

-- Update RLS if needed
ALTER POLICY "agent_reader_select" ON leads
USING (true);  -- Update policy logic
```

### 3. Test Locally

```powershell
# Reset DB with migrations
supabase db reset

# Verify
supabase db psql -c "SELECT * FROM leads LIMIT 1;"
```

### 4. Deploy

```powershell
# Push to remote
supabase db push

# Or via CI/CD
```

---

## Recent / Notable Migrations

### Atomic staging-lead promotion (RPC)

The system includes an optional migration that adds a PostgreSQL function for atomic promotion of a staging lead into primary tables:

- File: `supabase/migrations/20260124_atomic_promotion_rpc.sql`
- Function: `public.promote_staging_lead_atomic(p_staging_lead_id uuid, p_lead_id uuid) returns jsonb`

The Persistence promotion path will attempt this RPC first and fall back to the legacy multi-step copy/archive logic if the RPC is unavailable.

---

## Migration Patterns

### Add Column

```sql
ALTER TABLE leads
ADD COLUMN score INTEGER DEFAULT 0;
```

### Add Column (Non-Nullable)

```sql
-- Step 1: Add nullable
ALTER TABLE leads
ADD COLUMN source TEXT;

-- Step 2: Backfill
UPDATE leads SET source = 'unknown' WHERE source IS NULL;

-- Step 3: Add constraint
ALTER TABLE leads
ALTER COLUMN source SET NOT NULL;
```

### Create Table

```sql
CREATE TABLE campaigns (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id UUID NOT NULL REFERENCES clients(id),
    name TEXT NOT NULL,
    status TEXT DEFAULT 'draft',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE campaigns ENABLE ROW LEVEL SECURITY;

-- Create policies
CREATE POLICY "agent_reader_select" ON campaigns
FOR SELECT TO agent_reader
USING (true);

CREATE POLICY "agent_writer_all" ON campaigns
FOR ALL TO agent_writer
USING (true);
```

### Add Foreign Key

```sql
ALTER TABLE leads
ADD COLUMN campaign_id UUID REFERENCES campaigns(id);
```

### Create Index

```sql
-- Single column
CREATE INDEX idx_leads_status ON leads(status);

-- Composite
CREATE INDEX idx_leads_client_status ON leads(client_id, status);

-- Partial
CREATE INDEX idx_leads_active ON leads(status)
WHERE status != 'archived';
```

### Add Constraint

```sql
-- Check constraint
ALTER TABLE leads
ADD CONSTRAINT leads_status_check
CHECK (status IN ('new', 'contacted', 'qualified', 'converted', 'lost'));

-- Unique constraint
ALTER TABLE leads
ADD CONSTRAINT leads_email_client_unique
UNIQUE (email, client_id);
```

---

## RLS Migrations

### Create Policy

```sql
CREATE POLICY "agent_reader_select" ON leads
FOR SELECT
TO agent_reader
USING (true);
```

### Update Policy

```sql
-- Drop and recreate
DROP POLICY IF EXISTS "agent_reader_select" ON leads;

CREATE POLICY "agent_reader_select" ON leads
FOR SELECT
TO agent_reader
USING (
    (current_setting('request.jwt.claims', true)::json->>'role') = 'agent_reader'
);
```

### Tenant Isolation

```sql
CREATE POLICY "tenant_isolation" ON leads
FOR ALL
USING (
    tenant_id = (current_setting('request.jwt.claims', true)::json->>'tenant_id')
);
```

---

## Rollback

### Manual Rollback

Create a new migration that reverses changes:

```sql
-- supabase/migrations/20250115130000_revert_priority.sql
ALTER TABLE leads DROP COLUMN priority;
DROP INDEX IF EXISTS idx_leads_priority;
```

### Best Practice

Keep migrations small and reversible. Each migration should do one thing.

---

## Migration History

View applied migrations:

```powershell
supabase migration list
```

```
LOCAL  REMOTE  TIME
20250101000000  true  true  Initial schema
20250110000000  true  true  Add staging tables
20250115000000  true  false Add priority field
```

---

## Schema Dump

Export current schema:

```powershell
# Full schema
supabase db dump > schema.sql

# Data only
supabase db dump --data-only > data.sql
```

---

## CI/CD Integration

### GitHub Actions

```yaml
- name: Apply migrations
  run: |
    supabase link --project-ref ${{ secrets.SUPABASE_PROJECT_REF }}
    supabase db push
  env:
    SUPABASE_ACCESS_TOKEN: ${{ secrets.SUPABASE_ACCESS_TOKEN }}
```

---

## Troubleshooting

### Migration Failed

```powershell
# Check error
supabase db reset 2>&1 | Select-String -Pattern "ERROR"

# Fix migration file, then retry
supabase db reset
```

### Stuck Migration

```sql
-- Check migration table
SELECT * FROM supabase_migrations.schema_migrations;

-- Manually mark as applied (dangerous!)
INSERT INTO supabase_migrations.schema_migrations (version)
VALUES ('20250115120000');
```

### Sync Issues

```powershell
# Pull remote state
supabase db pull

# Compare
supabase db diff
```

## Related

- [Database Schema](schema.md)
- [Row-Level Security](rls.md)
- [Supabase Setup](../../getting-started/installation.md)
