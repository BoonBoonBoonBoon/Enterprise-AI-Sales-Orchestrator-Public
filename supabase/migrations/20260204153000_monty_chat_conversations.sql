-- ============================================================================
-- MONTY CHAT CONVERSATIONS (SESSIONS)
-- Groups monty_chats into separate conversations per user/lead
-- ============================================================================

-- Create enum for conversation status
DO $$ BEGIN
    CREATE TYPE monty_chat_status AS ENUM ('open', 'closed');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create the monty_chat_conversations table
CREATE TABLE IF NOT EXISTS public.monty_chat_conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Ownership & context
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    client_id UUID NOT NULL REFERENCES public.clients(id) ON DELETE CASCADE,
    lead_id UUID NOT NULL,  -- Can reference leads OR staging_leads
    lead_source TEXT NOT NULL CHECK (lead_source IN ('leads', 'staging_leads')),

    -- Status
    status monty_chat_status NOT NULL DEFAULT 'open',
    ended_at TIMESTAMPTZ,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Add conversation_id to monty_chats for grouping
ALTER TABLE public.monty_chats
    ADD COLUMN IF NOT EXISTS conversation_id UUID;

ALTER TABLE public.monty_chats
    ADD CONSTRAINT monty_chats_conversation_id_fkey
    FOREIGN KEY (conversation_id)
    REFERENCES public.monty_chat_conversations(id)
    ON DELETE SET NULL;

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_monty_chat_conversations_user_id ON public.monty_chat_conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_monty_chat_conversations_lead_id ON public.monty_chat_conversations(lead_id);
CREATE INDEX IF NOT EXISTS idx_monty_chat_conversations_status ON public.monty_chat_conversations(status);
CREATE INDEX IF NOT EXISTS idx_monty_chat_conversations_created_at ON public.monty_chat_conversations(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_monty_chat_conversations_user_lead ON public.monty_chat_conversations(user_id, lead_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_monty_chats_conversation_id ON public.monty_chats(conversation_id);

-- Enable RLS
ALTER TABLE public.monty_chat_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.monty_chat_conversations FORCE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY "Users can read own monty chat conversations"
    ON public.monty_chat_conversations
    FOR SELECT
    TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own monty chat conversations"
    ON public.monty_chat_conversations
    FOR INSERT
    TO authenticated
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own monty chat conversations"
    ON public.monty_chat_conversations
    FOR UPDATE
    TO authenticated
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own monty chat conversations"
    ON public.monty_chat_conversations
    FOR DELETE
    TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY "Service role has full access to monty chat conversations"
    ON public.monty_chat_conversations
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Grant permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON public.monty_chat_conversations TO authenticated;
GRANT ALL ON public.monty_chat_conversations TO service_role;

-- Comments
COMMENT ON TABLE public.monty_chat_conversations IS 'Groups monty_chats into per-user, per-lead conversations (sessions).';
COMMENT ON COLUMN public.monty_chat_conversations.lead_source IS 'Which table the lead comes from: leads or staging_leads';
