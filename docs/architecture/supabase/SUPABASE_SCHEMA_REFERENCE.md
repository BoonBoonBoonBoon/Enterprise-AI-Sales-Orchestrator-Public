# Supabase Schema Reference - RAG Agent Access

**Quick Reference:** All tables accessible by RAG Agent for enrichment operations.

---

## Primary Enrichment Tables

### `leads` (27 fields)
**Purpose:** Main lead storage with enrichment data  
**Required:** `id`, `client_id`, `email`, `first_name`, `last_name`

| Field | Type | Purpose |
|-------|------|---------|
| `id` | uuid | Primary key |
| `client_id` | uuid | Tenant isolation |
| `campaign_id` | uuid | Campaign association |
| `email` | text | Contact email (required) |
| `first_name` | text | Required |
| `last_name` | text | Required |
| `company_name` | text | For Crunchbase lookup |
| `job_title` | text | For qualification |
| `phone_number` | text | Optional contact |
| `current_status` | text | Lead lifecycle state |
| `sequence_step` | int8 | Current outreach step |
| `sequence_active` | bool | In active sequence? |
| `next_action_date` | timestamptz | Scheduled action |
| `last_contact_date` | timestamptz | Last touchpoint |
| `sent_timestamps` | jsonb | Email send history |
| `reply_timestamps` | jsonb | Reply history |
| `booking_status` | text | Meeting status |
| `re_engagement_date` | timestamptz | Follow-up timing |
| `generated_copy_subject` | text | Email subject |
| `generated_copy_body` | text | Email body |
| `crm_id` | text | External CRM reference |
| `last_reply_sentiment` | text | positive/negative/neutral |
| `lead_score` | int8 | 0-100 qualification score |
| `qualification_status` | text | qualified/disqualified/pending |
| **`enrichment_status`** | text | **pending/in_progress/completed/failed** |
| **`raw_data`** | jsonb | **Enriched API data (Crunchbase, LinkedIn)** |
| `created_at` | timestamptz | Record creation |
| `updated_at` | timestamptz | Last modification |

**Embedding Fields:** `company_name`, `job_title`, `current_status`, `qualification_status`

---

### `staging_leads` (22 fields)
**Purpose:** Pre-enrichment validation queue  
**Required:** `id`, `client_id`

| Field | Type | Purpose |
|-------|------|---------|
| `id` | uuid | Primary key |
| `client_id` | uuid | Tenant isolation |
| `campaign_id` | uuid | Campaign association |
| `source` | text | Lead source (Apollo, CSV, etc.) |
| `email` | text | Not required (may need validation) |
| `first_name` | text | May be incomplete |
| `last_name` | text | May be incomplete |
| `company_name` | text | For enrichment |
| `job_title` | text | For enrichment |
| `phone_number` | text | Optional |
| `linkedin_url` | text | For LinkedIn API lookup |
| `website_url` | text | For company data |
| `location` | text | Geographic data |
| `industry` | text | Industry classification |
| `company_size` | text | Employee count range |
| `revenue_range` | text | Company revenue |
| `raw_data` | jsonb | Pre-enrichment data |
| `duplicate_check_hash` | text | Deduplication key |
| `error_log` | text | Validation errors |
| `enrichment_status` | text | Enrichment progress |
| `qualification_status` | text | Qualification result |
| `promotion_ready` | bool | Ready to move to `leads`? |
| `archived_at` | timestamptz | Soft-delete for audit on promotion |
| `created_at` | timestamptz | Import timestamp |
| `updated_at` | timestamptz | Last update |

**Embedding Fields:** `company_name`, `industry`, `job_title`, `location`

**Workflow:** CSV Import → `staging_leads` → RAG Enrichment → Validation → Promote to `leads` (soft-delete staging row via `archived_at` once added; keep row for audit)

**Notes:**
- Soft-delete rather than hard-delete on promotion (add `archived_at` column if missing in the current schema).
- RAG cascade should read staging conversations/messages (see below) when a staging lead matches.

---

## Context Tables (RAG Can Read)

### `conversations` (7 fields)
**Purpose:** Email/SMS conversation threads  
**Required:** `id`, `client_id`, `channel`

| Field | Type | Purpose |
|-------|------|---------|
| `id` | uuid | Primary key |
| `client_id` | uuid | Tenant isolation |
| `lead_id` | uuid | Links to `leads` table |
| `channel` | text | email/sms/linkedin |
| `status` | text | active/closed |
| `summary` | text | AI-generated summary |
| `created_at` | timestamptz | Thread start |
| `updated_at` | timestamptz | Last message |

**Embedding Fields:** `summary`, `channel`

---

### `messages` (7 fields)
**Purpose:** Individual messages in conversations  
**Required:** `id`, `conversation_id`, `sender_type`

| Field | Type | Purpose |
|-------|------|---------|
| `id` | uuid | Primary key |
| `conversation_id` | uuid | Links to `conversations` |
| `sender_type` | text | agent/lead/system |
| `text_content` | text | Message body |
| `metadata` | text | Additional data |
| `sent_at` | text | Send timestamp |
| `created_at` | timestamptz | Record creation |

**Embedding Fields:** `text_content`

---

### `staging_conversations`
**Purpose:** Hold early-stage threads before a lead is promoted  
**Required:** `id`, `staging_lead_id`

| Field | Type | Purpose |
|-------|------|---------|
| `id` | uuid | Primary key |
| `staging_lead_id` | uuid | Links to `staging_leads` |
| `status` | text | active/closed |
| `metadata` | jsonb | Transport metadata (headers, thread ids) |
| `created_at` | timestamptz | Thread start |
| `updated_at` | timestamptz | Last message |
| `archived_at` | timestamptz | Soft-delete for audit |

**Embedding Fields:** None (RAG reads via cascade; embed downstream content as needed)

---

### `staging_messages`
**Purpose:** Individual messages tied to staging conversations  
**Required:** `id`, `staging_conversation_id`, `sender`, `receiver`, `content`

| Field | Type | Purpose |
|-------|------|---------|
| `id` | uuid | Primary key |
| `staging_conversation_id` | uuid | Links to `staging_conversations` |
| `sender` | text | Sender identifier |
| `receiver` | text | Receiver identifier |
| `content` | text | Message body |
| `sent_at` | timestamptz | Send timestamp |
| `metadata` | jsonb | Additional data (headers, message-id) |
| `created_at` | timestamptz | Record creation |
| `updated_at` | timestamptz | Last update |
| `archived_at` | timestamptz | Soft-delete for audit |

**Embedding Fields:** `content`

---

### `clients` (4 fields)
**Purpose:** Tenant/customer accounts  
**Required:** `id`, `name`

| Field | Type | Purpose |
|-------|------|---------|
| `id` | uuid | Primary key |
| `name` | text | Client name |
| `created_at` | timestamptz | Account creation |
| `updated_at` | timestamptz | Last update |

**Embedding Fields:** `name`

---

### `campaigns` (8 fields)
**Purpose:** Outreach campaigns  
**Required:** `id`, `client_id`, `campaign_name`

| Field | Type | Purpose |
|-------|------|---------|
| `id` | uuid | Primary key |
| `client_id` | uuid | Tenant isolation |
| `campaign_name` | text | Campaign identifier |
| `campaign_type` | text | email/linkedin/multi-channel |
| `status` | text | active/paused/completed |
| `sequence_id` | uuid | Links to `sequences` |
| `created_at` | timestamptz | Campaign start |
| `updated_at` | timestamptz | Last update |

**Embedding Fields:** `campaign_name`, `campaign_type`

---

### `sequences` (6 fields)
**Purpose:** Outreach sequence templates  
**Required:** `id`, `client_id`, `sequence_name`

| Field | Type | Purpose |
|-------|------|---------|
| `id` | uuid | Primary key |
| `client_id` | uuid | Tenant isolation |
| `sequence_name` | text | Sequence identifier |
| `steps` | jsonb | Array of sequence steps (day, channel, template) |
| `created_at` | timestamptz | Sequence creation |
| `updated_at` | timestamptz | Last update |

**Embedding Fields:** `sequence_name`

**Example `steps` JSONB:**
```json
[
  {"day": 0, "channel": "email", "template": "initial_intro"},
  {"day": 3, "channel": "linkedin", "template": "connection_request"},
  {"day": 7, "channel": "email", "template": "follow_up"}
]
```

---

## Operational Tables (System Use)

### `agent_tasks` (9 fields)
**Purpose:** Track agent task execution  
**Required:** `task_id`, `client_id`

| Field | Type | Purpose |
|-------|------|---------|
| `task_id` | uuid | Primary key |
| `client_id` | uuid | Tenant isolation |
| `status` | text | pending/in_progress/completed/failed |
| `input` | jsonb | Task input data |
| `output` | jsonb | Task result |
| `error` | text | Error message if failed |
| `workflow_id` | text | Parent workflow ID |
| `metadata` | jsonb | Additional context |
| `created_at` | timestamptz | Task start |
| `updated_at` | timestamptz | Last update |

---

### `agent_subtasks` (9 fields)
**Purpose:** Subtask tracking for orchestrators  
**Required:** `sub_task_id`

| Field | Type | Purpose |
|-------|------|---------|
| `sub_task_id` | uuid | Primary key |
| `parent_task_id` | uuid | Links to `agent_tasks` |
| `agent_name` | text | rag/copywriter/persistence |
| `status` | text | pending/completed/failed |
| `input` | jsonb | Subtask input |
| `output` | jsonb | Subtask result |
| `error` | text | Error if failed |
| `created_at` | timestamptz | Subtask start |
| `updated_at` | timestamptz | Last update |

---

### `audit_log` (7 fields)
**Purpose:** System audit trail  
**Required:** `id`, `client_id`

| Field | Type | Purpose |
|-------|------|---------|
| `id` | uuid | Primary key |
| `client_id` | uuid | Tenant isolation |
| `user_or_agent` | text | Who performed action |
| `action` | text | create/update/delete |
| `target_table` | text | Affected table |
| `target_id` | uuid | Affected record |
| `metadata` | jsonb | Additional context |
| `created_at` | timestamptz | Action timestamp |

---

## RAG Agent Operations

### Read Operations (All Tables)
RAG agent can query all 11 tables for enrichment context:
- **Leads:** Get lead details for enrichment
- **Staging Leads:** Process pre-enrichment queue
- **Conversations/Messages:** Analyze communication history for sentiment
- **Campaigns/Sequences:** Understand outreach context
- **Clients:** Multi-tenant filtering
- **Agent Tasks/Subtasks:** Track orchestration state
- **Audit Log:** Historical context

### Write Operations (Via Persistence Agent)
RAG agent delegates writes to Persistence Agent:
- **Primary:** Update `leads.raw_data` with enriched API responses
- **Primary:** Update `leads.enrichment_status` (pending → completed)
- **Secondary:** Update `staging_leads.enrichment_status`
- **Secondary:** Update `staging_leads.promotion_ready` = true

### Enrichment Workflow
1. **Input:** Lead record from `leads` or `staging_leads`
2. **Validation:** Check required fields (email, first_name, last_name, company_name)
3. **External APIs:** Call Crunchbase (company data) + LinkedIn (professional data)
4. **Storage:** Merge API responses into `raw_data` JSONB field
5. **Output:** Update `enrichment_status` = "completed", `lead_score`, `qualification_status`

---

## JSONB Field Structures

### `leads.raw_data` (Enriched Data)
```json
{
  "crunchbase": {
    "company_name": "Acme Corp",
    "website": "https://acme.com",
    "industry": "SaaS",
    "employee_count": 250,
    "founded_date": "2018-01-15",
    "headquarters": "San Francisco, CA",
    "total_funding": 50000000,
    "funding_stage": "Series B"
  },
  "linkedin": {
    "company_linkedin_id": "acme-corp",
    "company_size": "201-500",
    "person_linkedin_id": "john-doe",
    "headline": "VP of Sales at Acme Corp"
  },
  "enrichment_metadata": {
    "sources": ["crunchbase", "linkedin"],
    "confidence": 0.85,
    "enriched_at": "2025-11-29T10:30:00Z",
    "enriched_fields": ["company_info", "funding", "linkedin_person"]
  }
}
```

### `leads.sent_timestamps` / `reply_timestamps`
```json
{
  "email_1": "2025-11-25T09:00:00Z",
  "email_2": "2025-11-28T09:00:00Z"
}
```

### `sequences.steps`
```json
[
  {"day": 0, "channel": "email", "template": "initial_intro"},
  {"day": 3, "channel": "linkedin", "template": "connection_request"},
  {"day": 7, "channel": "phone", "template": "call_script"},
  {"day": 10, "channel": "email", "template": "follow_up"}
]
```

---

## Quick Reference: Table Relationships

```
clients
  ├─ campaigns
  │   └─ leads (campaign_id)
  ├─ staging_leads
  ├─ sequences
  │   └─ campaigns (sequence_id)
  ├─ conversations
  │   ├─ messages
  │   └─ leads (lead_id)
  └─ agent_tasks
      └─ agent_subtasks
```

---

## Common Queries

### Get Lead with Enrichment Data
```sql
SELECT 
  id, email, first_name, last_name, company_name, job_title,
  enrichment_status, lead_score, qualification_status,
  raw_data->'crunchbase'->>'industry' as industry,
  raw_data->'crunchbase'->>'employee_count' as company_size,
  raw_data->'crunchbase'->>'funding_stage' as funding_stage
FROM leads
WHERE client_id = 'your-client-uuid'
AND enrichment_status = 'completed';
```

### Get Staging Leads Ready for Promotion
```sql
SELECT *
FROM staging_leads
WHERE client_id = 'your-client-uuid'
AND promotion_ready = true
AND enrichment_status = 'completed';
```

### Get Campaign Performance
```sql
SELECT 
  c.campaign_name,
  COUNT(l.id) as total_leads,
  COUNT(l.id) FILTER (WHERE l.qualification_status = 'qualified') as qualified_leads,
  COUNT(l.id) FILTER (WHERE l.booking_status = 'confirmed') as booked_meetings
FROM campaigns c
LEFT JOIN leads l ON l.campaign_id = c.id
WHERE c.client_id = 'your-client-uuid'
GROUP BY c.id, c.campaign_name;
```

---

**Last Updated:** November 29, 2025  
**Schema Version:** RAG Agent v1.0  
**Total Tables:** 11
