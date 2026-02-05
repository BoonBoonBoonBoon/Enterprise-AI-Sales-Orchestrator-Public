-- ============================================================================
-- MONTY COPILOT ENHANCEMENTS
-- Adds title, summary, and optional link to outreach conversations
-- ============================================================================

-- Add title and summary to conversations for better UX
ALTER TABLE public.monty_chat_conversations
    ADD COLUMN IF NOT EXISTS title TEXT,
    ADD COLUMN IF NOT EXISTS summary TEXT,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

-- Optional link to outreach conversation (for context about what the copilot helped with)
ALTER TABLE public.monty_chat_conversations
    ADD COLUMN IF NOT EXISTS related_conversation_id UUID,
    ADD COLUMN IF NOT EXISTS related_conversation_source TEXT CHECK (related_conversation_source IN ('conversations', 'staging_conversations'));

-- Add metadata for extensibility (e.g., tags, AI model used, etc.)
ALTER TABLE public.monty_chat_conversations
    ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;

-- Add message count for quick display without counting
ALTER TABLE public.monty_chat_conversations
    ADD COLUMN IF NOT EXISTS message_count INTEGER DEFAULT 0;

-- ============================================================================
-- FUNCTION: Auto-update message_count on insert to monty_chats
-- ============================================================================

CREATE OR REPLACE FUNCTION update_monty_conversation_message_count()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.conversation_id IS NOT NULL THEN
        UPDATE public.monty_chat_conversations
        SET message_count = (
            SELECT COUNT(*) FROM public.monty_chats 
            WHERE conversation_id = NEW.conversation_id
        ),
        updated_at = now()
        WHERE id = NEW.conversation_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Drop trigger if exists, then create
DROP TRIGGER IF EXISTS trigger_update_monty_message_count ON public.monty_chats;

CREATE TRIGGER trigger_update_monty_message_count
    AFTER INSERT ON public.monty_chats
    FOR EACH ROW
    EXECUTE FUNCTION update_monty_conversation_message_count();

-- ============================================================================
-- FUNCTION: Auto-update updated_at on conversation change
-- ============================================================================

CREATE OR REPLACE FUNCTION update_monty_conversation_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_monty_conversation_timestamp ON public.monty_chat_conversations;

CREATE TRIGGER trigger_update_monty_conversation_timestamp
    BEFORE UPDATE ON public.monty_chat_conversations
    FOR EACH ROW
    EXECUTE FUNCTION update_monty_conversation_timestamp();

-- ============================================================================
-- FUNCTION: Auto-generate title from first user message
-- ============================================================================

CREATE OR REPLACE FUNCTION auto_title_monty_conversation()
RETURNS TRIGGER AS $$
DECLARE
    conv_title TEXT;
BEGIN
    -- Only process if this is the first user message in the conversation
    IF NEW.conversation_id IS NOT NULL AND NEW.role = 'user' THEN
        SELECT title INTO conv_title 
        FROM public.monty_chat_conversations 
        WHERE id = NEW.conversation_id;
        
        -- If no title yet, set one from the first 50 chars of the message
        IF conv_title IS NULL OR conv_title = '' THEN
            UPDATE public.monty_chat_conversations
            SET title = LEFT(NEW.content, 50) || CASE WHEN LENGTH(NEW.content) > 50 THEN '...' ELSE '' END
            WHERE id = NEW.conversation_id;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS trigger_auto_title_monty_conversation ON public.monty_chats;

CREATE TRIGGER trigger_auto_title_monty_conversation
    AFTER INSERT ON public.monty_chats
    FOR EACH ROW
    EXECUTE FUNCTION auto_title_monty_conversation();

-- ============================================================================
-- INDEXES for new columns
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_monty_chat_conversations_updated_at 
    ON public.monty_chat_conversations(updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_monty_chat_conversations_related 
    ON public.monty_chat_conversations(related_conversation_id) 
    WHERE related_conversation_id IS NOT NULL;

-- ============================================================================
-- VIEW: Prospect copilot history (for prospect profile page)
-- ============================================================================

CREATE OR REPLACE VIEW public.v_prospect_copilot_history AS
SELECT 
    c.id,
    c.user_id,
    c.client_id,
    c.lead_id,
    c.lead_source,
    c.title,
    c.summary,
    c.status,
    c.message_count,
    c.related_conversation_id,
    c.related_conversation_source,
    c.metadata,
    c.created_at,
    c.updated_at,
    c.ended_at,
    -- Get the user's email for display
    u.email as user_email,
    -- Get the first message preview
    (
        SELECT content 
        FROM public.monty_chats m 
        WHERE m.conversation_id = c.id 
        ORDER BY m.created_at ASC 
        LIMIT 1
    ) as first_message_preview
FROM public.monty_chat_conversations c
LEFT JOIN auth.users u ON c.user_id = u.id;

-- Grant access to the view
GRANT SELECT ON public.v_prospect_copilot_history TO authenticated;
GRANT SELECT ON public.v_prospect_copilot_history TO service_role;

-- RLS on view (inherits from base table)
ALTER VIEW public.v_prospect_copilot_history OWNER TO postgres;

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON COLUMN public.monty_chat_conversations.title IS 'Auto-generated or user-set title for the conversation';
COMMENT ON COLUMN public.monty_chat_conversations.summary IS 'AI-generated or user-set summary of the conversation';
COMMENT ON COLUMN public.monty_chat_conversations.related_conversation_id IS 'Optional FK to conversations or staging_conversations (outreach context)';
COMMENT ON COLUMN public.monty_chat_conversations.related_conversation_source IS 'Which table the related conversation comes from';
COMMENT ON COLUMN public.monty_chat_conversations.metadata IS 'Flexible JSON for tags, AI model info, etc.';
COMMENT ON COLUMN public.monty_chat_conversations.message_count IS 'Cached count of messages (auto-updated by trigger)';

COMMENT ON VIEW public.v_prospect_copilot_history IS 'Convenient view for displaying copilot conversation history on prospect profiles';
