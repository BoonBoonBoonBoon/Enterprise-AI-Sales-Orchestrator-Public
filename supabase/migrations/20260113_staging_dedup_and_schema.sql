-- Migration: Staging Leads & Conversations Deduplication + Schema Enhancements
-- Date: 2026-01-13
-- Purpose: 
--   1. Add UNIQUE constraint on staging_leads.email (per client) to prevent duplicate leads
--   2. Add UNIQUE constraint on staging_conversations to prevent duplicate convos
--   3. Add descriptive columns to staging_conversations and staging_messages
--   4. Define clear rules for what constitutes a "new conversation"
--
-- DEDUPLICATION RULES:
--   - staging_leads: One lead per email per client (email + client_id is unique)
--   - staging_conversations: One conversation per lead + subject (or thread_id if present)
--   - staging_messages: One message per conversation + message_id (already exists)

-- ============================================================================
-- PART 1: STAGING_LEADS DEDUPLICATION
-- ============================================================================

-- PRE-DEDUP: If duplicates already exist, the unique index creation will fail.
-- We keep the oldest active row per (client_id, email) and archive the rest.
WITH ranked AS (
    SELECT
        id,
        client_id,
        email,
        created_at,
        ROW_NUMBER() OVER (
            PARTITION BY client_id, email
            ORDER BY created_at ASC NULLS LAST, id ASC
        ) AS rn
    FROM public.staging_leads
    WHERE archived_at IS NULL
      AND email IS NOT NULL
)
UPDATE public.staging_leads sl
SET archived_at = NOW(),
    updated_at = NOW()
FROM ranked r
WHERE sl.id = r.id
  AND r.rn > 1;

-- Add unique constraint on email per client (only for non-archived leads)
-- This allows upsert with ON CONFLICT (client_id, email) to work properly
DROP INDEX IF EXISTS ux_staging_leads_client_email;
CREATE UNIQUE INDEX ux_staging_leads_client_email 
    ON public.staging_leads (client_id, email) 
    WHERE email IS NOT NULL AND archived_at IS NULL;

COMMENT ON INDEX ux_staging_leads_client_email IS 
    'Ensures one active staging lead per email per client. Allows upsert deduplication.';

-- ============================================================================
-- PART 2: STAGING_CONVERSATIONS DEDUPLICATION
-- ============================================================================

-- PRE-DEDUP: If duplicates already exist, the unique index creation will fail.
-- We keep the oldest active row per (staging_lead_id, subject) and archive the rest.
WITH ranked AS (
    SELECT
        id,
        staging_lead_id,
        subject,
        created_at,
        ROW_NUMBER() OVER (
            PARTITION BY staging_lead_id, subject
            ORDER BY created_at ASC NULLS LAST, id ASC
        ) AS rn
    FROM public.staging_conversations
    WHERE archived_at IS NULL
      AND subject IS NOT NULL
)
UPDATE public.staging_conversations sc
SET archived_at = NOW(),
    updated_at = NOW()
FROM ranked r
WHERE sc.id = r.id
  AND r.rn > 1;

-- Add unique constraint on staging_lead_id + subject for non-archived conversations
-- This prevents creating multiple conversations for the same lead + subject
DROP INDEX IF EXISTS ux_staging_conversations_lead_subject;
CREATE UNIQUE INDEX ux_staging_conversations_lead_subject 
    ON public.staging_conversations (staging_lead_id, subject) 
    WHERE subject IS NOT NULL AND archived_at IS NULL;

COMMENT ON INDEX ux_staging_conversations_lead_subject IS 
    'Ensures one active conversation per staging lead + subject. New subject = new conversation.';

-- Note: ux_staging_conversations_lead_thread already exists for thread_id matching

-- ============================================================================
-- PART 3: STAGING_CONVERSATIONS SCHEMA ENHANCEMENTS
-- ============================================================================

-- Add descriptive columns for better conversation tracking
ALTER TABLE public.staging_conversations 
    ADD COLUMN IF NOT EXISTS message_count INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS first_message_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_message_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_sender VARCHAR(255),
    ADD COLUMN IF NOT EXISTS summary TEXT;

-- Add comments for clarity
COMMENT ON COLUMN public.staging_conversations.message_count IS 
    'Total number of messages in this conversation thread';
COMMENT ON COLUMN public.staging_conversations.first_message_at IS 
    'Timestamp of the first message in this conversation';
COMMENT ON COLUMN public.staging_conversations.last_message_at IS 
    'Timestamp of the most recent message (for sorting/activity tracking)';
COMMENT ON COLUMN public.staging_conversations.last_sender IS 
    'Email address of the last person who sent a message';
COMMENT ON COLUMN public.staging_conversations.summary IS 
    'AI-generated or manual summary of the conversation thread';
COMMENT ON COLUMN public.staging_conversations.subject IS 
    'Email subject line - used for conversation grouping when thread_id is absent';
COMMENT ON COLUMN public.staging_conversations.thread_id IS 
    'Email thread ID from mail headers - primary dedup key when present';
COMMENT ON COLUMN public.staging_conversations.channel IS 
    'Communication channel: email, linkedin, phone, chat, etc.';
COMMENT ON COLUMN public.staging_conversations.status IS 
    'Conversation status: open, closed, pending_reply, needs_attention';

-- ============================================================================
-- PART 4: STAGING_MESSAGES SCHEMA ENHANCEMENTS
-- ============================================================================

-- Add descriptive columns for better message classification
ALTER TABLE public.staging_messages 
    ADD COLUMN IF NOT EXISTS direction VARCHAR(20) DEFAULT 'inbound',
    ADD COLUMN IF NOT EXISTS email_type VARCHAR(50);

-- Add check constraint for direction
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'staging_messages_direction_check'
    ) THEN
        ALTER TABLE public.staging_messages 
            ADD CONSTRAINT staging_messages_direction_check 
            CHECK (direction IN ('inbound', 'outbound'));
    END IF;
END $$;

-- Add comments for clarity
COMMENT ON COLUMN public.staging_messages.direction IS 
    'Message direction: inbound (from lead) or outbound (to lead)';
COMMENT ON COLUMN public.staging_messages.email_type IS 
    'Type of email: inquiry, reply, follow_up, auto_reply, bounce, etc.';
COMMENT ON COLUMN public.staging_messages.sender IS 
    'Email address of the message sender';
COMMENT ON COLUMN public.staging_messages.receiver IS 
    'Email address of the message recipient';
COMMENT ON COLUMN public.staging_messages.content IS 
    'Full text content of the message body';
COMMENT ON COLUMN public.staging_messages.message_id IS 
    'Unique message ID from email headers - used for deduplication';
COMMENT ON COLUMN public.staging_messages.metadata IS 
    'Additional message metadata: headers, attachments, labels, etc.';

-- ============================================================================
-- PART 5: TRIGGER TO AUTO-UPDATE CONVERSATION STATS
-- ============================================================================

-- Function to update conversation stats when a message is added
CREATE OR REPLACE FUNCTION update_staging_conversation_stats()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE public.staging_conversations
    SET 
        message_count = COALESCE(message_count, 0) + 1,
        first_message_at = COALESCE(first_message_at, NEW.sent_at),
        last_message_at = NEW.sent_at,
        last_sender = NEW.sender,
        updated_at = NOW()
    WHERE id = NEW.staging_conversation_id;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger (drop first if exists to allow re-running migration)
DROP TRIGGER IF EXISTS trg_staging_message_stats ON public.staging_messages;
CREATE TRIGGER trg_staging_message_stats
    AFTER INSERT ON public.staging_messages
    FOR EACH ROW
    EXECUTE FUNCTION update_staging_conversation_stats();

-- ============================================================================
-- PART 6: INDEX IMPROVEMENTS
-- ============================================================================

-- Index for finding active conversations by last activity (useful for dashboards)
DROP INDEX IF EXISTS idx_staging_conversations_last_activity;
CREATE INDEX idx_staging_conversations_last_activity 
    ON public.staging_conversations (last_message_at DESC NULLS LAST) 
    WHERE archived_at IS NULL;

-- Index for direction-based queries on messages
DROP INDEX IF EXISTS idx_staging_messages_direction;
CREATE INDEX idx_staging_messages_direction 
    ON public.staging_messages (staging_conversation_id, direction);

-- ============================================================================
-- DOCUMENTATION: DEDUPLICATION RULES
-- ============================================================================

COMMENT ON TABLE public.staging_leads IS 
'Pre-qualification queue for inbound leads.

DEDUPLICATION: One lead per (client_id, email) pair.
- When same email contacts again, we UPDATE the existing staging_lead
- Use upsert with ON CONFLICT (client_id, email) WHERE archived_at IS NULL

LIFECYCLE: pending → enriched → qualified/disqualified → promoted (to leads table)';

COMMENT ON TABLE public.staging_conversations IS 
'Email conversation threads for staging leads (pre-qualification).

DEDUPLICATION RULES:
1. If thread_id present: Group by (staging_lead_id, thread_id)
2. If no thread_id: Group by (staging_lead_id, subject)
3. New subject from same lead = NEW conversation

WHEN TO CREATE NEW CONVERSATION:
- New thread_id from an existing lead
- New subject line from an existing lead  
- First message from a new lead

STATUS VALUES: open, closed, pending_reply, needs_attention';

COMMENT ON TABLE public.staging_messages IS 
'Individual messages within staging conversations.

DEDUPLICATION: One message per (staging_conversation_id, message_id)
- message_id from email headers ensures we never store duplicates
- Trigger auto-updates parent conversation stats

DIRECTION: inbound = from lead, outbound = our reply';
