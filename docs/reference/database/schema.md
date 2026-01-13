# Database Schema

Complete reference for all database tables in the Agentic System.

## Entity Relationship Diagram

```
┌─────────────┐
│   clients   │
└──────┬──────┘
       │ 1:N
       ▼
┌─────────────┐     ┌─────────────────┐
│  campaigns  │     │  staging_leads  │ (no FK)
└──────┬──────┘     └────────┬────────┘
       │ N:1                 │ 1:N
       ▼                     ▼
┌─────────────┐     ┌───────────────────────┐
│    leads    │     │ staging_conversations │
└──────┬──────┘     └───────────┬───────────┘
       │ 1:N                    │ 1:N
       ▼                        ▼
┌───────────────┐   ┌──────────────────────┐
│ conversations │   │   staging_messages   │
└───────┬───────┘   └──────────────────────┘
        │ 1:N
        ▼
┌─────────────┐
│  messages   │
└─────────────┘
```

## Core Tables

### clients

Top-level tenant entity.

| Column       | Type        | Nullable | Default             | Description         |
| ------------ | ----------- | -------- | ------------------- | ------------------- |
| `id`         | uuid        | ❌       | `gen_random_uuid()` | Primary key         |
| `name`       | text        | ❌       | —                   | Client/company name |
| `email`      | text        | ✅       | —                   | Contact email       |
| `settings`   | jsonb       | ✅       | `{}`                | Configuration       |
| `created_at` | timestamptz | ❌       | `now()`             | Creation time       |
| `updated_at` | timestamptz | ✅       | —                   | Last update         |

```sql
CREATE TABLE clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    email TEXT,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ
);
```

### campaigns

Marketing campaigns under a client.

| Column       | Type        | Nullable | Default             | Description       |
| ------------ | ----------- | -------- | ------------------- | ----------------- |
| `id`         | uuid        | ❌       | `gen_random_uuid()` | Primary key       |
| `client_id`  | uuid        | ❌       | —                   | FK → clients      |
| `name`       | text        | ❌       | —                   | Campaign name     |
| `status`     | text        | ❌       | `'draft'`           | Status            |
| `template`   | text        | ✅       | —                   | Outreach template |
| `settings`   | jsonb       | ✅       | `{}`                | Campaign config   |
| `created_at` | timestamptz | ❌       | `now()`             | Creation time     |

```sql
CREATE TABLE campaigns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id),
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    template TEXT,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### leads

Qualified leads associated with a client and campaign.

| Column        | Type        | Nullable | Default             | Description         |
| ------------- | ----------- | -------- | ------------------- | ------------------- |
| `id`          | uuid        | ❌       | `gen_random_uuid()` | Primary key         |
| `client_id`   | uuid        | ❌       | —                   | FK → clients        |
| `campaign_id` | uuid        | ❌       | —                   | FK → campaigns      |
| `name`        | text        | ✅       | —                   | Lead name           |
| `email`       | text        | ❌       | —                   | Lead email          |
| `company`     | text        | ✅       | —                   | Company name        |
| `role`        | text        | ✅       | —                   | Job title           |
| `status`      | text        | ❌       | `'new'`             | Lead status         |
| `score`       | integer     | ✅       | —                   | Qualification score |
| `enrichment`  | jsonb       | ✅       | `{}`                | Enrichment data     |
| `metadata`    | jsonb       | ✅       | `{}`                | Additional data     |
| `created_at`  | timestamptz | ❌       | `now()`             | Creation time       |
| `updated_at`  | timestamptz | ✅       | —                   | Last update         |

```sql
CREATE TABLE leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id),
    campaign_id UUID NOT NULL REFERENCES campaigns(id),
    name TEXT,
    email TEXT NOT NULL,
    company TEXT,
    role TEXT,
    status TEXT NOT NULL DEFAULT 'new',
    score INTEGER,
    enrichment JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ
);
```

### conversations

Email threads with a lead.

| Column            | Type        | Nullable | Default             | Description     |
| ----------------- | ----------- | -------- | ------------------- | --------------- |
| `id`              | uuid        | ❌       | `gen_random_uuid()` | Primary key     |
| `lead_id`         | uuid        | ❌       | —                   | FK → leads      |
| `subject`         | text        | ✅       | —                   | Thread subject  |
| `status`          | text        | ❌       | `'active'`          | Thread status   |
| `last_message_at` | timestamptz | ✅       | —                   | Last activity   |
| `metadata`        | jsonb       | ✅       | `{}`                | Thread metadata |
| `created_at`      | timestamptz | ❌       | `now()`             | Creation time   |

```sql
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID NOT NULL REFERENCES leads(id),
    subject TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    last_message_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### messages

Individual messages in a conversation.

| Column            | Type        | Nullable | Default             | Description                 |
| ----------------- | ----------- | -------- | ------------------- | --------------------------- |
| `id`              | uuid        | ❌       | `gen_random_uuid()` | Primary key                 |
| `conversation_id` | uuid        | ❌       | —                   | FK → conversations          |
| `content`         | text        | ❌       | —                   | Message body                |
| `direction`       | text        | ❌       | —                   | `'inbound'` or `'outbound'` |
| `sent_at`         | timestamptz | ✅       | —                   | When sent                   |
| `metadata`        | jsonb       | ❌       | —                   | **Required!** Use `{}`      |
| `created_at`      | timestamptz | ❌       | `now()`             | Creation time               |

!!! warning "metadata is NOT NULL"
Always include `"metadata": {}` when inserting messages.

```sql
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id),
    content TEXT NOT NULL,
    direction TEXT NOT NULL,
    sent_at TIMESTAMPTZ,
    metadata JSONB NOT NULL,  -- NOT NULL!
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## Staging Tables

Pre-qualification tables for inbound leads before promotion.

### staging_leads

| Column        | Type        | Nullable | Default             | Description   |
| ------------- | ----------- | -------- | ------------------- | ------------- |
| `id`          | uuid        | ❌       | `gen_random_uuid()` | Primary key   |
| `email`       | text        | ❌       | —                   | Lead email    |
| `name`        | text        | ✅       | —                   | Lead name     |
| `source`      | text        | ✅       | —                   | Lead source   |
| `raw_data`    | jsonb       | ✅       | `{}`                | Original data |
| `archived_at` | timestamptz | ✅       | —                   | Soft delete   |
| `created_at`  | timestamptz | ❌       | `now()`             | Creation time |

### staging_conversations

| Column            | Type        | Nullable | Default             |
| ----------------- | ----------- | -------- | ------------------- |
| `id`              | uuid        | ❌       | `gen_random_uuid()` |
| `staging_lead_id` | uuid        | ❌       | FK → staging_leads  |
| `subject`         | text        | ✅       | —                   |
| `archived_at`     | timestamptz | ✅       | —                   |
| `created_at`      | timestamptz | ❌       | `now()`             |

### staging_messages

| Column                    | Type        | Nullable | Default                    |
| ------------------------- | ----------- | -------- | -------------------------- |
| `id`                      | uuid        | ❌       | `gen_random_uuid()`        |
| `staging_conversation_id` | uuid        | ❌       | FK → staging_conversations |
| `content`                 | text        | ❌       | —                          |
| `direction`               | text        | ❌       | —                          |
| `metadata`                | jsonb       | ❌       | —                          |
| `archived_at`             | timestamptz | ✅       | —                          |
| `created_at`              | timestamptz | ❌       | `now()`                    |

## Lead Promotion

When promoting staging leads to qualified leads:

```sql
-- 1. Create lead
INSERT INTO leads (client_id, campaign_id, email, name, ...)
SELECT <client_id>, <campaign_id>, email, name, ...
FROM staging_leads
WHERE id = <staging_lead_id>;

-- 2. Create conversation
INSERT INTO conversations (lead_id, subject, ...)
SELECT <new_lead_id>, subject, ...
FROM staging_conversations
WHERE staging_lead_id = <staging_lead_id>;

-- 3. Copy messages
INSERT INTO messages (conversation_id, content, direction, metadata, ...)
SELECT <new_conv_id>, content, direction, metadata, ...
FROM staging_messages
WHERE staging_conversation_id = <staging_conv_id>;

-- 4. Soft delete staging (keep history)
UPDATE staging_leads SET archived_at = now() WHERE id = <staging_lead_id>;
UPDATE staging_conversations SET archived_at = now() WHERE staging_lead_id = <staging_lead_id>;
UPDATE staging_messages SET archived_at = now() WHERE staging_conversation_id IN (...);
```

## Indexes

Recommended indexes for performance:

```sql
-- Lead lookups
CREATE INDEX idx_leads_email ON leads(email);
CREATE INDEX idx_leads_status ON leads(status);
CREATE INDEX idx_leads_client_id ON leads(client_id);

-- Conversation queries
CREATE INDEX idx_conversations_lead_id ON conversations(lead_id);
CREATE INDEX idx_messages_conversation_id ON messages(conversation_id);

-- Staging lookups
CREATE INDEX idx_staging_leads_email ON staging_leads(email);
CREATE INDEX idx_staging_leads_not_archived ON staging_leads(id) WHERE archived_at IS NULL;
```

## Insertion Order

Due to foreign key constraints, insert in this order:

```
1. clients
2. campaigns (requires client_id)
3. leads (requires client_id, campaign_id)
4. conversations (requires lead_id)
5. messages (requires conversation_id)
```

## Related

- [RLS Policies](rls.md) — Row-level security
- [Persistence Agent](../../components/tier-3/persistence.md)
- [RAG Agent](../../components/tier-3/rag.md)
