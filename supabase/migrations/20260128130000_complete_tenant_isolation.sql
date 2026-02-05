-- Migration: Complete tenant isolation for all tables
-- Date: 2026-01-28
-- Purpose: Add RLS policies for remaining tenant-owned tables

-- ============================================================================
-- 1. MESSAGES TABLE - Needs client_id for direct RLS, or join through conversation
-- ============================================================================
-- Messages don't have client_id directly, they belong to conversations
-- We need to either:
-- A) Add client_id column to messages (denormalization for performance)
-- B) Use a function that looks up via conversation->lead->client_id
-- Going with option B for now to avoid schema changes

-- Enable RLS on messages
ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;

-- Create a function to get client_id from a conversation
CREATE OR REPLACE FUNCTION public.get_client_id_from_conversation(conv_id UUID) RETURNS UUID
    LANGUAGE sql STABLE SECURITY DEFINER
    AS $$
    SELECT c.client_id FROM public.conversations c WHERE c.id = conv_id LIMIT 1;
$$;

-- Messages: users can only access messages in their tenant's conversations
DROP POLICY IF EXISTS "tenant_isolation_messages" ON public.messages;
CREATE POLICY "tenant_isolation_messages" ON public.messages
    FOR ALL
    USING (
        public.get_client_id_from_conversation(conversation_id) = public.get_current_client_id()
        OR public.get_user_role() IN ('agent_reader', 'agent_writer')
    );

-- Service role full access
DROP POLICY IF EXISTS "service_role_messages" ON public.messages;
CREATE POLICY "service_role_messages" ON public.messages
    TO service_role
    USING (true) WITH CHECK (true);

-- ============================================================================
-- 2. STAGING_LEADS TABLE
-- ============================================================================
ALTER TABLE public.staging_leads ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "tenant_isolation_staging_leads" ON public.staging_leads;
CREATE POLICY "tenant_isolation_staging_leads" ON public.staging_leads
    FOR ALL
    USING (
        client_id = public.get_current_client_id()
        OR public.get_user_role() IN ('agent_reader', 'agent_writer')
    );

DROP POLICY IF EXISTS "service_role_staging_leads" ON public.staging_leads;
CREATE POLICY "service_role_staging_leads" ON public.staging_leads
    TO service_role
    USING (true) WITH CHECK (true);

-- ============================================================================
-- 3. STAGING_CONVERSATIONS TABLE
-- ============================================================================
-- staging_conversations -> staging_leads -> client_id
ALTER TABLE public.staging_conversations ENABLE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION public.get_client_id_from_staging_lead(sl_id UUID) RETURNS UUID
    LANGUAGE sql STABLE SECURITY DEFINER
    AS $$
    SELECT sl.client_id FROM public.staging_leads sl WHERE sl.id = sl_id LIMIT 1;
$$;

DROP POLICY IF EXISTS "tenant_isolation_staging_conversations" ON public.staging_conversations;
CREATE POLICY "tenant_isolation_staging_conversations" ON public.staging_conversations
    FOR ALL
    USING (
        public.get_client_id_from_staging_lead(staging_lead_id) = public.get_current_client_id()
        OR public.get_user_role() IN ('agent_reader', 'agent_writer')
    );

DROP POLICY IF EXISTS "service_role_staging_conversations" ON public.staging_conversations;
CREATE POLICY "service_role_staging_conversations" ON public.staging_conversations
    TO service_role
    USING (true) WITH CHECK (true);

-- ============================================================================
-- 4. STAGING_MESSAGES TABLE
-- ============================================================================
-- staging_messages -> staging_conversations -> staging_leads -> client_id
ALTER TABLE public.staging_messages ENABLE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION public.get_client_id_from_staging_conversation(sc_id UUID) RETURNS UUID
    LANGUAGE sql STABLE SECURITY DEFINER
    AS $$
    SELECT public.get_client_id_from_staging_lead(sc.staging_lead_id) 
    FROM public.staging_conversations sc WHERE sc.id = sc_id LIMIT 1;
$$;

DROP POLICY IF EXISTS "tenant_isolation_staging_messages" ON public.staging_messages;
CREATE POLICY "tenant_isolation_staging_messages" ON public.staging_messages
    FOR ALL
    USING (
        public.get_client_id_from_staging_conversation(staging_conversation_id) = public.get_current_client_id()
        OR public.get_user_role() IN ('agent_reader', 'agent_writer')
    );

DROP POLICY IF EXISTS "service_role_staging_messages" ON public.staging_messages;
CREATE POLICY "service_role_staging_messages" ON public.staging_messages
    TO service_role
    USING (true) WITH CHECK (true);

-- ============================================================================
-- 5. SEQUENCES TABLE
-- ============================================================================
ALTER TABLE public.sequences ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "tenant_isolation_sequences" ON public.sequences;
CREATE POLICY "tenant_isolation_sequences" ON public.sequences
    FOR ALL
    USING (
        client_id = public.get_current_client_id()
        OR public.get_user_role() IN ('agent_reader', 'agent_writer')
    );

DROP POLICY IF EXISTS "service_role_sequences" ON public.sequences;
CREATE POLICY "service_role_sequences" ON public.sequences
    TO service_role
    USING (true) WITH CHECK (true);

-- ============================================================================
-- 6. AGENT_TASKS TABLE
-- ============================================================================
ALTER TABLE public.agent_tasks ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "tenant_isolation_agent_tasks" ON public.agent_tasks;
CREATE POLICY "tenant_isolation_agent_tasks" ON public.agent_tasks
    FOR ALL
    USING (
        client_id = public.get_current_client_id()
        OR public.get_user_role() IN ('agent_reader', 'agent_writer')
    );

DROP POLICY IF EXISTS "service_role_agent_tasks" ON public.agent_tasks;
CREATE POLICY "service_role_agent_tasks" ON public.agent_tasks
    TO service_role
    USING (true) WITH CHECK (true);

-- ============================================================================
-- 7. AGENT_SUBTASKS TABLE
-- ============================================================================
-- agent_subtasks -> agent_tasks -> client_id
ALTER TABLE public.agent_subtasks ENABLE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION public.get_client_id_from_agent_task(task_id UUID) RETURNS UUID
    LANGUAGE sql STABLE SECURITY DEFINER
    AS $$
    SELECT at.client_id FROM public.agent_tasks at WHERE at."Task id" = task_id LIMIT 1;
$$;

DROP POLICY IF EXISTS "tenant_isolation_agent_subtasks" ON public.agent_subtasks;
CREATE POLICY "tenant_isolation_agent_subtasks" ON public.agent_subtasks
    FOR ALL
    USING (
        public.get_client_id_from_agent_task(parent_task_id) = public.get_current_client_id()
        OR public.get_user_role() IN ('agent_reader', 'agent_writer')
    );

DROP POLICY IF EXISTS "service_role_agent_subtasks" ON public.agent_subtasks;
CREATE POLICY "service_role_agent_subtasks" ON public.agent_subtasks
    TO service_role
    USING (true) WITH CHECK (true);

-- ============================================================================
-- 8. USER_ROLES TABLE - Already has RLS, ensure tenant-aware
-- ============================================================================
-- user_roles is per-user, not per-tenant. Keep existing policies.
-- Users should only see their own roles.
ALTER TABLE public.user_roles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "users_see_own_roles" ON public.user_roles;
CREATE POLICY "users_see_own_roles" ON public.user_roles
    FOR SELECT
    USING (user_id = auth.uid());

DROP POLICY IF EXISTS "service_role_user_roles" ON public.user_roles;
CREATE POLICY "service_role_user_roles" ON public.user_roles
    TO service_role
    USING (true) WITH CHECK (true);

-- ============================================================================
-- 9. CREATE MAILBOXES TABLE (if not exists) with proper RLS
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.mailboxes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES public.clients(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    provider TEXT NOT NULL DEFAULT 'gmail' CHECK (provider IN ('gmail', 'outlook', 'imap')),
    display_name TEXT,
    is_active BOOLEAN DEFAULT true,
    oauth_credentials JSONB,  -- Encrypted in practice
    last_sync_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(client_id, email)
);

-- Trigger for updated_at
DROP TRIGGER IF EXISTS update_mailboxes_updated_at ON public.mailboxes;
CREATE TRIGGER update_mailboxes_updated_at
    BEFORE UPDATE ON public.mailboxes
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.mailboxes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "tenant_isolation_mailboxes" ON public.mailboxes;
CREATE POLICY "tenant_isolation_mailboxes" ON public.mailboxes
    FOR ALL
    USING (client_id = public.get_current_client_id());

DROP POLICY IF EXISTS "service_role_mailboxes" ON public.mailboxes;
CREATE POLICY "service_role_mailboxes" ON public.mailboxes
    TO service_role
    USING (true) WITH CHECK (true);

-- ============================================================================
-- 10. CREATE DRAFTS TABLE with proper RLS
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.drafts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES public.clients(id) ON DELETE CASCADE,
    lead_id UUID REFERENCES public.leads(id) ON DELETE SET NULL,
    conversation_id UUID REFERENCES public.conversations(id) ON DELETE SET NULL,
    mailbox_id UUID REFERENCES public.mailboxes(id) ON DELETE SET NULL,
    subject TEXT,
    body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'sent', 'edited')),
    context_used JSONB,  -- RAG context that was retrieved
    generation_metadata JSONB,  -- Model, tokens, etc.
    rejection_reason TEXT,
    approved_by UUID REFERENCES auth.users(id),
    approved_at TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

DROP TRIGGER IF EXISTS update_drafts_updated_at ON public.drafts;
CREATE TRIGGER update_drafts_updated_at
    BEFORE UPDATE ON public.drafts
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.drafts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "tenant_isolation_drafts" ON public.drafts;
CREATE POLICY "tenant_isolation_drafts" ON public.drafts
    FOR ALL
    USING (client_id = public.get_current_client_id());

DROP POLICY IF EXISTS "service_role_drafts" ON public.drafts;
CREATE POLICY "service_role_drafts" ON public.drafts
    TO service_role
    USING (true) WITH CHECK (true);

-- ============================================================================
-- 11. INDEXES FOR NEW TABLES
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_mailboxes_client_id ON public.mailboxes(client_id);
CREATE INDEX IF NOT EXISTS idx_drafts_client_id ON public.drafts(client_id);
CREATE INDEX IF NOT EXISTS idx_drafts_status ON public.drafts(status);
CREATE INDEX IF NOT EXISTS idx_drafts_lead_id ON public.drafts(lead_id);
CREATE INDEX IF NOT EXISTS idx_staging_leads_client_id ON public.staging_leads(client_id);

-- ============================================================================
-- 12. GRANT PERMISSIONS
-- ============================================================================
GRANT SELECT, INSERT, UPDATE, DELETE ON public.mailboxes TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.drafts TO authenticated;
GRANT ALL ON public.mailboxes TO service_role;
GRANT ALL ON public.drafts TO service_role;
