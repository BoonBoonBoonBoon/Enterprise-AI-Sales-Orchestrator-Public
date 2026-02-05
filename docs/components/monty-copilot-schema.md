# Monty Copilot Database Schema

This document describes the database tables and relationships for the Monty Copilot feature.

## Tables Overview

```
┌─────────────────────────────────┐      ┌────────────────────────────────┐
│   monty_chat_conversations      │      │          monty_chats           │
│   (Conversation Sessions)       │◄─────│      (Individual Messages)     │
├─────────────────────────────────┤      ├────────────────────────────────┤
│ id (PK)                         │      │ id (PK)                        │
│ user_id → auth.users            │      │ user_id → auth.users           │
│ client_id → clients             │      │ client_id → clients            │
│ lead_id                         │      │ lead_id                        │
│ lead_source                     │      │ lead_source                    │
│ title                           │      │ conversation_id → (FK)         │
│ summary                         │      │ role (user/assistant/system)   │
│ status (open/closed)            │      │ content                        │
│ message_count                   │      │ model                          │
│ related_conversation_id         │      │ tokens_used                    │
│ related_conversation_source     │      │ context_summary                │
│ metadata (JSONB)                │      │ created_at                     │
│ created_at                      │      └────────────────────────────────┘
│ updated_at                      │
│ ended_at                        │
└─────────────────────────────────┘
           │
           │ lead_id + lead_source
           ▼
┌─────────────────────────────────┐      ┌────────────────────────────────┐
│          leads                  │      │       staging_leads            │
│   (Qualified Leads)             │      │    (Pre-qualified Leads)       │
├─────────────────────────────────┤      ├────────────────────────────────┤
│ id (PK)                         │      │ id (PK)                        │
│ client_id → clients             │      │ client_id → clients            │
│ campaign_id → campaigns         │      │ campaign_id → campaigns        │
│ email, first_name, last_name    │      │ email, first_name, last_name   │
│ company_name, job_title         │      │ company_name, job_title        │
│ ...                             │      │ ...                            │
└─────────────────────────────────┘      └────────────────────────────────┘
```

## Table Details

### `monty_chat_conversations`

Groups individual messages into conversation sessions. Each conversation is:

- Owned by a specific **user** (the team member using copilot)
- Associated with a **client** (multi-tenant isolation)
- Related to a specific **lead** (prospect being discussed)

| Column                        | Type        | Description                                 |
| ----------------------------- | ----------- | ------------------------------------------- |
| `id`                          | UUID        | Primary key                                 |
| `user_id`                     | UUID        | FK to auth.users - the team member          |
| `client_id`                   | UUID        | FK to clients - tenant isolation            |
| `lead_id`                     | UUID        | Reference to lead (soft FK)                 |
| `lead_source`                 | TEXT        | 'leads' or 'staging_leads'                  |
| `title`                       | TEXT        | Auto-generated from first message           |
| `summary`                     | TEXT        | AI-generated or manual summary              |
| `status`                      | ENUM        | 'open' or 'closed'                          |
| `message_count`               | INT         | Cached count (trigger-updated)              |
| `related_conversation_id`     | UUID        | Optional link to outreach conversation      |
| `related_conversation_source` | TEXT        | 'conversations' or 'staging_conversations'  |
| `metadata`                    | JSONB       | Flexible storage for tags, model info, etc. |
| `created_at`                  | TIMESTAMPTZ | When conversation started                   |
| `updated_at`                  | TIMESTAMPTZ | Last activity timestamp                     |
| `ended_at`                    | TIMESTAMPTZ | When conversation was closed                |

### `monty_chats`

Individual messages exchanged between user and AI.

| Column            | Type        | Description                        |
| ----------------- | ----------- | ---------------------------------- |
| `id`              | UUID        | Primary key                        |
| `user_id`         | UUID        | FK to auth.users                   |
| `client_id`       | UUID        | FK to clients                      |
| `lead_id`         | UUID        | Reference to lead                  |
| `lead_source`     | TEXT        | 'leads' or 'staging_leads'         |
| `conversation_id` | UUID        | FK to monty_chat_conversations     |
| `role`            | ENUM        | 'user', 'assistant', or 'system'   |
| `content`         | TEXT        | Message text (max 32,000 chars)    |
| `model`           | TEXT        | AI model used (e.g., 'gpt-4o')     |
| `tokens_used`     | INT         | Token consumption for this message |
| `context_summary` | TEXT        | Summary of lead context provided   |
| `created_at`      | TIMESTAMPTZ | When message was sent              |

### `monty_rate_limits`

Per-user rate limiting for API usage control.

| Column            | Type        | Description                        |
| ----------------- | ----------- | ---------------------------------- |
| `user_id`         | UUID        | PK, FK to auth.users               |
| `requests_today`  | INT         | Count of requests today            |
| `last_request_at` | TIMESTAMPTZ | Last request timestamp             |
| `daily_limit`     | INT         | Max requests per day (default 100) |
| `reset_at`        | TIMESTAMPTZ | When counter resets                |

## Views

### `v_prospect_copilot_history`

Convenient view for displaying copilot history on prospect profiles.

```sql
SELECT * FROM v_prospect_copilot_history
WHERE lead_id = 'uuid-here' AND lead_source = 'leads'
ORDER BY created_at DESC;
```

Returns all columns from `monty_chat_conversations` plus:

- `user_email` - Email of the team member
- `first_message_preview` - First message content for preview

## Triggers

### `trigger_update_monty_message_count`

Automatically updates `message_count` in `monty_chat_conversations` when a new message is inserted.

### `trigger_auto_title_monty_conversation`

Automatically sets `title` from the first user message (truncated to 50 chars).

### `trigger_update_monty_conversation_timestamp`

Automatically updates `updated_at` when conversation is modified.

## Row Level Security (RLS)

All tables have RLS enabled with policies ensuring:

- Users can only access their own chat data
- Service role has full access for API operations
- Multi-tenant isolation via client_id

## Example Queries

### Start a new conversation

```sql
INSERT INTO monty_chat_conversations (user_id, client_id, lead_id, lead_source)
VALUES ('user-uuid', 'client-uuid', 'lead-uuid', 'leads')
RETURNING id;
```

### Add a message

```sql
INSERT INTO monty_chats (user_id, client_id, lead_id, lead_source, conversation_id, role, content, model)
VALUES ('user-uuid', 'client-uuid', 'lead-uuid', 'leads', 'conv-uuid', 'user', 'Hello!', 'gpt-4o');
```

### Get conversation history for a lead

```sql
SELECT * FROM v_prospect_copilot_history
WHERE lead_id = 'lead-uuid' AND lead_source = 'leads'
ORDER BY updated_at DESC;
```

### Get messages in a conversation

```sql
SELECT role, content, created_at FROM monty_chats
WHERE conversation_id = 'conv-uuid'
ORDER BY created_at ASC;
```

### Close a conversation

```sql
UPDATE monty_chat_conversations
SET status = 'closed', ended_at = now()
WHERE id = 'conv-uuid';
```

## Migration Files

1. `20260204150000_monty_chats_table.sql` - Base messages table
2. `20260204153000_monty_chat_conversations.sql` - Conversation sessions
3. `20260205100000_monty_copilot_enhancements.sql` - Enhanced fields, triggers, view
