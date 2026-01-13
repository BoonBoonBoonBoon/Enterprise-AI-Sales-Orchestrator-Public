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
