-- ============================================================================
-- MONTY COPILOT CHAT HISTORY TABLE
-- Per-user, per-lead AI assistant conversations with full RLS security
-- ============================================================================

-- Create enum for message roles
DO $$ BEGIN
    CREATE TYPE monty_message_role AS ENUM ('user', 'assistant', 'system');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create the monty_chats table
CREATE TABLE IF NOT EXISTS public.monty_chats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Ownership & context
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    client_id UUID NOT NULL REFERENCES public.clients(id) ON DELETE CASCADE,
    lead_id UUID NOT NULL,  -- Can reference leads OR staging_leads
    lead_source TEXT NOT NULL CHECK (lead_source IN ('leads', 'staging_leads')),
    
    -- Message content
    role monty_message_role NOT NULL,
    content TEXT NOT NULL,
    
    -- Metadata
    model TEXT,  -- e.g., 'gpt-4o', 'claude-3-opus'
    tokens_used INTEGER,
    context_summary TEXT,  -- Summary of lead context used for this message
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    -- Constraints
    CONSTRAINT content_not_empty CHECK (char_length(content) > 0),
    CONSTRAINT content_max_length CHECK (char_length(content) <= 32000)
);

-- Enable RLS
ALTER TABLE public.monty_chats ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.monty_chats FORCE ROW LEVEL SECURITY;

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_monty_chats_user_id ON public.monty_chats(user_id);
CREATE INDEX IF NOT EXISTS idx_monty_chats_lead_id ON public.monty_chats(lead_id);
CREATE INDEX IF NOT EXISTS idx_monty_chats_client_id ON public.monty_chats(client_id);
CREATE INDEX IF NOT EXISTS idx_monty_chats_created_at ON public.monty_chats(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_monty_chats_user_lead ON public.monty_chats(user_id, lead_id, created_at DESC);

-- RLS Policies

-- Users can only read their own chat messages
CREATE POLICY "Users can read own monty chats"
    ON public.monty_chats
    FOR SELECT
    TO authenticated
    USING (auth.uid() = user_id);

-- Users can only insert their own chat messages
CREATE POLICY "Users can insert own monty chats"
    ON public.monty_chats
    FOR INSERT
    TO authenticated
    WITH CHECK (auth.uid() = user_id);

-- Users can delete their own chat history
CREATE POLICY "Users can delete own monty chats"
    ON public.monty_chats
    FOR DELETE
    TO authenticated
    USING (auth.uid() = user_id);

-- Service role has full access (for API endpoints)
CREATE POLICY "Service role has full access to monty chats"
    ON public.monty_chats
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Grant permissions
GRANT SELECT, INSERT, DELETE ON public.monty_chats TO authenticated;
GRANT ALL ON public.monty_chats TO service_role;

-- Comments
COMMENT ON TABLE public.monty_chats IS 'Stores per-user, per-lead AI assistant (Monty) conversation history';
COMMENT ON COLUMN public.monty_chats.lead_source IS 'Which table the lead comes from: leads or staging_leads';
COMMENT ON COLUMN public.monty_chats.context_summary IS 'Brief summary of the lead context provided to the AI for this exchange';

-- ============================================================================
-- RATE LIMITING TABLE (optional, for tracking API usage)
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.monty_rate_limits (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    requests_today INTEGER NOT NULL DEFAULT 0,
    last_request_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    daily_limit INTEGER NOT NULL DEFAULT 100,
    reset_at TIMESTAMPTZ NOT NULL DEFAULT (date_trunc('day', now()) + interval '1 day')
);

ALTER TABLE public.monty_rate_limits ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.monty_rate_limits FORCE ROW LEVEL SECURITY;

-- Users can only see/update their own rate limits
CREATE POLICY "Users can read own rate limits"
    ON public.monty_rate_limits
    FOR SELECT
    TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY "Users can update own rate limits"
    ON public.monty_rate_limits
    FOR UPDATE
    TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own rate limits"
    ON public.monty_rate_limits
    FOR INSERT
    TO authenticated
    WITH CHECK (auth.uid() = user_id);

-- Service role has full access (for API endpoints)
CREATE POLICY "Service role has full access to rate limits"
    ON public.monty_rate_limits
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE ON public.monty_rate_limits TO authenticated;
GRANT ALL ON public.monty_rate_limits TO service_role;

COMMENT ON TABLE public.monty_rate_limits IS 'Tracks per-user daily API usage for rate limiting';
