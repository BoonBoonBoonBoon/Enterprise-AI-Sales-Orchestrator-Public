-- Staging conversations/messages and soft-delete for staging leads
-- Apply in Supabase SQL editor or migration runner

-- 1) Soft-delete support for staging leads
ALTER TABLE staging_leads
  ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ NULL;

-- 2) Staging conversations (threads before qualification)
CREATE TABLE IF NOT EXISTS staging_conversations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    staging_lead_id     UUID NOT NULL REFERENCES staging_leads(id) ON DELETE CASCADE,
  thread_id           VARCHAR(255) NULL,
  subject             TEXT NULL,
  channel             VARCHAR(50) NOT NULL DEFAULT 'email',
    status              VARCHAR(50) NOT NULL DEFAULT 'active',
    metadata            JSONB NOT NULL DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    archived_at         TIMESTAMPTZ NULL
);

-- 3) Staging messages (per staging conversation)
CREATE TABLE IF NOT EXISTS staging_messages (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    staging_conversation_id  UUID NOT NULL REFERENCES staging_conversations(id) ON DELETE CASCADE,
    sender                   VARCHAR(255) NOT NULL,
    receiver                 VARCHAR(255) NOT NULL,
    content                  TEXT NOT NULL,
    sent_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
  message_id               VARCHAR(255) NULL,
    metadata                 JSONB NOT NULL DEFAULT '{}',
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    archived_at              TIMESTAMPTZ NULL
);

-- 4) Helpful indexes
CREATE INDEX IF NOT EXISTS idx_staging_leads_email ON staging_leads (email);
CREATE INDEX IF NOT EXISTS idx_staging_conversations_lead ON staging_conversations (staging_lead_id);
CREATE INDEX IF NOT EXISTS idx_staging_messages_conv ON staging_messages (staging_conversation_id);
CREATE INDEX IF NOT EXISTS idx_staging_conversations_thread ON staging_conversations (staging_lead_id, thread_id);
CREATE INDEX IF NOT EXISTS idx_staging_messages_message ON staging_messages (staging_conversation_id, message_id);
