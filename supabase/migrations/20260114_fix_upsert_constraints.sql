-- Migration: Fix Unique Constraints for ON CONFLICT Upsert Support
-- Date: 2026-01-14
-- Purpose: 
--   PostgreSQL's ON CONFLICT clause cannot use partial (conditional) indexes.
--   We need non-partial unique constraints for upsert operations to work.
--
-- SOLUTION:
--   1. Drop the partial unique indexes (WHERE archived_at IS NULL)
--   2. Add a "_archived_email" column to hold the email when a row is soft-deleted
--   3. Create a trigger to nullify email on archive (preserving it in _archived_email)
--   4. Create non-partial unique constraints
--
-- This allows:
--   - ON CONFLICT (client_id, email) to work correctly
--   - Archived rows don't conflict (their email is NULL)
--   - Original email is preserved in _archived_email for audit

-- ============================================================================
-- PART 1: STAGING_LEADS CONSTRAINT FIX
-- ============================================================================

-- Step 1: Add column to preserve original email when archived
ALTER TABLE public.staging_leads 
    ADD COLUMN IF NOT EXISTS _archived_email VARCHAR(255);

COMMENT ON COLUMN public.staging_leads._archived_email IS 
    'Stores the original email when a row is soft-deleted. Email is set to NULL on archive to allow new rows with same email.';

-- Step 2: Create trigger function to handle archival
CREATE OR REPLACE FUNCTION staging_leads_archive_handler()
RETURNS TRIGGER AS $$
BEGIN
    -- On archive: preserve email in _archived_email, set email to NULL
    IF NEW.archived_at IS NOT NULL AND OLD.archived_at IS NULL THEN
        NEW._archived_email := OLD.email;
        NEW.email := NULL;
    END IF;
    -- On unarchive: restore email from _archived_email
    IF NEW.archived_at IS NULL AND OLD.archived_at IS NOT NULL THEN
        NEW.email := COALESCE(NEW.email, OLD._archived_email);
        NEW._archived_email := NULL;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Step 3: Create trigger (drop if exists to avoid duplicates)
DROP TRIGGER IF EXISTS staging_leads_archive_trigger ON public.staging_leads;
CREATE TRIGGER staging_leads_archive_trigger
    BEFORE UPDATE ON public.staging_leads
    FOR EACH ROW
    EXECUTE FUNCTION staging_leads_archive_handler();

-- Step 4: Fix any existing archived rows (move email to _archived_email, set email NULL)
UPDATE public.staging_leads
SET _archived_email = email,
    email = NULL
WHERE archived_at IS NOT NULL 
  AND email IS NOT NULL;

-- Step 5: Drop the old partial index and create non-partial unique constraint
DROP INDEX IF EXISTS ux_staging_leads_client_email;
ALTER TABLE public.staging_leads 
    DROP CONSTRAINT IF EXISTS ux_staging_leads_client_email_constraint;
ALTER TABLE public.staging_leads 
    ADD CONSTRAINT ux_staging_leads_client_email_constraint 
    UNIQUE (client_id, email);

COMMENT ON CONSTRAINT ux_staging_leads_client_email_constraint ON public.staging_leads IS 
    'Non-partial unique constraint for ON CONFLICT upsert support. Archived rows have NULL email.';

-- ============================================================================
-- PART 2: STAGING_CONVERSATIONS CONSTRAINT FIX
-- ============================================================================

-- Step 1: Add column to preserve original subject when archived
ALTER TABLE public.staging_conversations 
    ADD COLUMN IF NOT EXISTS _archived_subject TEXT;

-- Step 2: Create trigger function for staging_conversations
CREATE OR REPLACE FUNCTION staging_conversations_archive_handler()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.archived_at IS NOT NULL AND OLD.archived_at IS NULL THEN
        NEW._archived_subject := OLD.subject;
        NEW.subject := NULL;
    END IF;
    IF NEW.archived_at IS NULL AND OLD.archived_at IS NOT NULL THEN
        NEW.subject := COALESCE(NEW.subject, OLD._archived_subject);
        NEW._archived_subject := NULL;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS staging_conversations_archive_trigger ON public.staging_conversations;
CREATE TRIGGER staging_conversations_archive_trigger
    BEFORE UPDATE ON public.staging_conversations
    FOR EACH ROW
    EXECUTE FUNCTION staging_conversations_archive_handler();

-- Step 3: Fix existing archived rows
UPDATE public.staging_conversations
SET _archived_subject = subject,
    subject = NULL
WHERE archived_at IS NOT NULL 
  AND subject IS NOT NULL;

-- Step 4: Drop partial index, create non-partial constraint
DROP INDEX IF EXISTS ux_staging_conversations_lead_subject;
ALTER TABLE public.staging_conversations 
    DROP CONSTRAINT IF EXISTS ux_staging_conversations_lead_subject_constraint;
ALTER TABLE public.staging_conversations 
    ADD CONSTRAINT ux_staging_conversations_lead_subject_constraint 
    UNIQUE (staging_lead_id, subject);

-- ============================================================================
-- PART 3: STAGING_MESSAGES - Already has non-partial constraint, just verify
-- ============================================================================

-- The staging_messages table should already have a proper constraint
-- Just ensure it exists (idempotent)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'ux_staging_messages_conversation_message_id_constraint'
    ) THEN
        -- Check if there's an index we need to convert
        DROP INDEX IF EXISTS ux_staging_messages_conversation_message_id;
        ALTER TABLE public.staging_messages 
            ADD CONSTRAINT ux_staging_messages_conversation_message_id_constraint 
            UNIQUE (staging_conversation_id, message_id);
    END IF;
END $$;

-- ============================================================================
-- VERIFICATION QUERY (run manually to confirm)
-- ============================================================================
-- SELECT 
--     c.conname AS constraint_name,
--     t.relname AS table_name,
--     pg_get_constraintdef(c.oid) AS constraint_definition
-- FROM pg_constraint c
-- JOIN pg_class t ON c.conrelid = t.oid
-- WHERE t.relname IN ('staging_leads', 'staging_conversations', 'staging_messages')
--   AND c.contype = 'u'
-- ORDER BY t.relname, c.conname;
