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

Auth + tenant access control (Supabase Auth + public schema):

```
auth.users 1:1 public.user_profiles

auth.users N:M public.clients via public.user_client_memberships

public.clients 1:N public.mailboxes
public.clients 1:N public.drafts
```

## How These Tables Are Used At Runtime

This schema is used by different parts of the 3-tier system (and the Gateway) in different ways.

### Table Families (roles)

- **Tenant + Access Control**: `clients`, `user_client_memberships`, `pending_invitations`, `user_roles`, `audit_log`
  - Purpose: establish tenant membership and enforce tenant isolation.
  - Key idea: `user_client_memberships` is the persistent user→tenant mapping; `pending_invitations` is temporary onboarding.
- **Canonical CRM History**: `campaigns`, `sequences`, `leads`, `conversations`, `messages`
  - Purpose: long-lived “source of truth” for qualified leads and their communication history.
- **Staging (pre-qualification)**: `staging_leads`, `staging_conversations`, `staging_messages`
  - Purpose: inbound holding area before a lead is promoted to canonical records.
  - Promotion copies staging conversations/messages into canonical tables, then soft-archives staging via `archived_at`.
- **Outbound Artifacts**: `mailboxes`, `drafts`
  - Purpose: sending identities (`mailboxes`) and approval/sending lifecycle objects (`drafts`).
  - Distinction: a `draft` is “candidate outbound content”; a `message` is part of the conversation timeline.

### Runtime Ownership Map (who reads/writes what)

| Component                        | Reads                                                                                              | Writes                                                        | Notes                                                                                                                                                         |
| -------------------------------- | -------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Portal (UI)**                  | `clients`, `user_profiles` (self/current-tenant), Supabase Auth                                    | `user_profiles` (self), Supabase Auth metadata                | Uses Supabase Auth for sign-in. Tenant-wide admin operations should go through the Gateway; limited self-scoped reads/writes may happen directly in early UX. |
| **Gateway (FastAPI)**            | `user_client_memberships`, `audit_log`                                                             | `pending_invitations`, `user_client_memberships`, `audit_log` | Auth + admin flows: invite users, accept invites (via SQL RPC), manage members.                                                                               |
| **Tier 1: ManagerAgent**         | —                                                                                                  | —                                                             | Routes work via Redis Streams only; no DB reads/writes by design.                                                                                             |
| **Tier 2: LeadsOrchestrator**    | (via RAG Agent)                                                                                    | (via Persistence Agent)                                       | Decides whether inbound goes to staging vs canonical; triggers promotion by delegating `promote_staging_lead`.                                                |
| **Tier 2: OutreachOrchestrator** | — (today)                                                                                          | — (today)                                                     | Coordinates campaigns + delegates content generation. Persistence of `drafts`/`mailboxes` is expected to be wired via Gateway/Persistence as the UI matures.  |
| **Tier 3: RAGAgent**             | `leads`, `staging_leads`, `conversations`, `staging_conversations`, `messages`, `staging_messages` | —                                                             | Read-only context retrieval for replies (falls back to staging when lead not yet promoted).                                                                   |
| **Tier 3: PersistenceAgent**     | `staging_*` (for promotion copy)                                                                   | `staging_leads`, `leads`, `conversations`, `messages`         | Primarily write-focused. Promotion reads staging rows to copy into canonical, then archives staging.                                                          |
| **Tier 3: CopywriterAgent**      | —                                                                                                  | —                                                             | Generates copy; does not directly persist drafts/messages.                                                                                                    |

!!! note "Why staging _and_ canonical?"
Staging tables allow you to ingest and deduplicate inbound threads before deciding to create a qualified `lead`. Canonical tables power ongoing conversation history, campaign reporting, and stable identifiers for long-lived workflows.

## Core Tables

### clients

Top-level tenant entity.

| Column                    | Type        | Nullable | Default             | Description                   |
| ------------------------- | ----------- | -------- | ------------------- | ----------------------------- |
| `id`                      | uuid        | ❌       | `gen_random_uuid()` | Primary key                   |
| `name`                    | text        | ❌       | —                   | Client/company name           |
| `legal_name`              | text        | ✅       | —                   | Registered legal entity name  |
| `domain`                  | text        | ✅       | —                   | Primary domain                |
| `website_url`             | text        | ✅       | —                   | Website                       |
| `industry`                | text        | ✅       | —                   | Industry vertical             |
| `company_size`            | text        | ✅       | —                   | Size band (e.g., 1-10, 11-50) |
| `timezone`                | text        | ✅       | `UTC`               | IANA timezone                 |
| `locale`                  | text        | ✅       | `en-US`             | Locale code                   |
| `status`                  | text        | ❌       | `active`            | Client status                 |
| `plan`                    | text        | ✅       | `standard`          | Subscription plan             |
| `billing_status`          | text        | ✅       | `active`            | Billing status                |
| `billing_email`           | text        | ✅       | —                   | Billing contact email         |
| `support_email`           | text        | ✅       | —                   | Support contact email         |
| `phone`                   | text        | ✅       | —                   | Main phone                    |
| `address_line1`           | text        | ✅       | —                   | Address line 1                |
| `address_line2`           | text        | ✅       | —                   | Address line 2                |
| `city`                    | text        | ✅       | —                   | City                          |
| `state`                   | text        | ✅       | —                   | State/region                  |
| `postal_code`             | text        | ✅       | —                   | Postal/ZIP                    |
| `country`                 | text        | ✅       | —                   | Country                       |
| `primary_contact_name`    | text        | ✅       | —                   | Primary contact name          |
| `primary_contact_title`   | text        | ✅       | —                   | Primary contact title         |
| `primary_contact_email`   | text        | ✅       | —                   | Primary contact email         |
| `primary_contact_phone`   | text        | ✅       | —                   | Primary contact phone         |
| `settings`                | jsonb       | ✅       | `{}`                | General configuration         |
| `portal_settings`         | jsonb       | ✅       | `{}`                | Portal-specific configuration |
| `features`                | jsonb       | ✅       | `{}`                | Feature flags / entitlements  |
| `metadata`                | jsonb       | ✅       | `{}`                | Additional metadata           |
| `stripe_customer_id`      | text        | ✅       | —                   | Stripe customer id            |
| `subscribed_at`           | timestamptz | ✅       | —                   | Subscription start            |
| `trial_ends_at`           | timestamptz | ✅       | —                   | Trial end time                |
| `canceled_at`             | timestamptz | ✅       | —                   | Cancellation time             |
| `onboarding_status`       | text        | ✅       | `pending`           | Onboarding state              |
| `onboarding_completed_at` | timestamptz | ✅       | —                   | Onboarding completion time    |
| `created_at`              | timestamptz | ❌       | `now()`             | Creation time                 |
| `updated_at`              | timestamptz | ✅       | —                   | Last update                   |

```sql
CREATE TABLE clients (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  legal_name TEXT,
  domain TEXT,
  website_url TEXT,
  industry TEXT,
  company_size TEXT,
  timezone TEXT DEFAULT 'UTC',
  locale TEXT DEFAULT 'en-US',
  status TEXT NOT NULL DEFAULT 'active',
  plan TEXT DEFAULT 'standard',
  billing_status TEXT DEFAULT 'active',
  billing_email TEXT,
  support_email TEXT,
  phone TEXT,
  address_line1 TEXT,
  address_line2 TEXT,
  city TEXT,
  state TEXT,
  postal_code TEXT,
  country TEXT,
  primary_contact_name TEXT,
  primary_contact_title TEXT,
  primary_contact_email TEXT,
  primary_contact_phone TEXT,
  settings JSONB DEFAULT '{}',
  portal_settings JSONB DEFAULT '{}',
  features JSONB DEFAULT '{}',
  metadata JSONB DEFAULT '{}',
  stripe_customer_id TEXT,
  subscribed_at TIMESTAMPTZ,
  trial_ends_at TIMESTAMPTZ,
  canceled_at TIMESTAMPTZ,
  onboarding_status TEXT DEFAULT 'pending',
  onboarding_completed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ
);
```

### user_client_memberships

Persistent mapping of a Supabase Auth user → client tenant membership.

| Column       | Type        | Nullable | Default  | Description                              |
| ------------ | ----------- | -------- | -------- | ---------------------------------------- |
| `user_id`    | uuid        | ❌       | —        | FK → `auth.users(id)`                    |
| `client_id`  | uuid        | ❌       | —        | FK → `public.clients(id)`                |
| `role`       | text        | ❌       | `member` | `admin` / `member` / `viewer`            |
| `created_at` | timestamptz | ✅       | `now()`  | Creation time                            |
| `updated_at` | timestamptz | ✅       | `now()`  | Updated via `update_updated_at_column()` |

Notes:

- Primary key is composite: `(user_id, client_id)`.
- On signup, the provisioning trigger inserts an admin membership for the newly created tenant.

### user_profiles

User-facing profile fields that the portal can safely read/update (self-scoped) without overloading `auth.users` metadata.

| Column       | Type        | Nullable | Default | Description               |
| ------------ | ----------- | -------- | ------- | ------------------------- |
| `user_id`    | uuid        | ❌       | —       | PK + FK → `auth.users`    |
| `client_id`  | uuid        | ✅       | —       | FK → `public.clients`     |
| `email`      | text        | ✅       | —       | Cached email              |
| `full_name`  | text        | ✅       | —       | Display name              |
| `phone`      | text        | ✅       | —       | Phone                     |
| `avatar_url` | text        | ✅       | —       | Avatar URL                |
| `metadata`   | jsonb       | ✅       | `{}`    | Extra structured metadata |
| `created_at` | timestamptz | ❌       | `now()` | Creation time             |
| `updated_at` | timestamptz | ❌       | `now()` | Updated via trigger       |

Notes:

- A provisioning trigger upserts `user_profiles` from `auth.users` on INSERT/UPDATE so portal identity stays consistent.

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

## Outbound Artifact Tables

These tables support sending identities and outbound content lifecycle.

### mailboxes

Sending identities (per tenant).

| Column         | Type        | Nullable | Default             | Description                              |
| -------------- | ----------- | -------- | ------------------- | ---------------------------------------- |
| `id`           | uuid        | ❌       | `gen_random_uuid()` | Primary key                              |
| `client_id`    | uuid        | ❌       | —                   | FK → clients (tenant scope)              |
| `email`        | text        | ❌       | —                   | Mailbox email                            |
| `provider`     | text        | ❌       | `gmail`             | `gmail` / `outlook` / `imap`             |
| `display_name` | text        | ✅       | —                   | Friendly name                            |
| `is_active`    | boolean     | ✅       | `true`              | Active/inactive                          |
| `created_at`   | timestamptz | ✅       | `now()`             | Creation time                            |
| `updated_at`   | timestamptz | ✅       | `now()`             | Updated via `update_updated_at_column()` |

Notes:

- Uniqueness: `(client_id, email)`.
- A BEFORE INSERT trigger may default `client_id` from `public.get_current_client_id()` when omitted.

### drafts

Outbound draft content (per tenant), optionally linked to a lead/conversation/mailbox.

| Column            | Type        | Nullable | Default             | Description                              |
| ----------------- | ----------- | -------- | ------------------- | ---------------------------------------- |
| `id`              | uuid        | ❌       | `gen_random_uuid()` | Primary key                              |
| `client_id`       | uuid        | ❌       | —                   | FK → clients (tenant scope)              |
| `lead_id`         | uuid        | ✅       | —                   | FK → leads                               |
| `conversation_id` | uuid        | ✅       | —                   | FK → conversations                       |
| `mailbox_id`      | uuid        | ✅       | —                   | FK → mailboxes                           |
| `subject`         | text        | ✅       | —                   | Draft subject                            |
| `body`            | text        | ❌       | —                   | Draft body                               |
| `status`          | text        | ❌       | `pending`           | `pending/approved/rejected/sent`         |
| `created_at`      | timestamptz | ✅       | `now()`             | Creation time                            |
| `updated_at`      | timestamptz | ✅       | `now()`             | Updated via `update_updated_at_column()` |

Notes:

- A BEFORE INSERT trigger may default `client_id` from `public.get_current_client_id()` when omitted.

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
