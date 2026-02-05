-- Migration: RLS for user_client_memberships
-- Date: 2026-02-03
-- Purpose: Connect users to clients with secure tenant-aware access

-- Ensure table exists (created earlier in tenant resolution migration)
CREATE TABLE IF NOT EXISTS public.user_client_memberships (
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    client_id UUID REFERENCES public.clients(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('admin', 'member', 'viewer')),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (user_id, client_id)
);

-- Indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_user_client_memberships_user_id ON public.user_client_memberships(user_id);
CREATE INDEX IF NOT EXISTS idx_user_client_memberships_client_id ON public.user_client_memberships(client_id);

-- Enable RLS
ALTER TABLE public.user_client_memberships ENABLE ROW LEVEL SECURITY;

-- Users can see their own memberships
DROP POLICY IF EXISTS user_memberships_self_read ON public.user_client_memberships;
CREATE POLICY user_memberships_self_read ON public.user_client_memberships
    FOR SELECT
    USING (user_id = auth.uid());

-- Tenant admins can manage memberships for their client
DROP POLICY IF EXISTS user_memberships_admin_manage ON public.user_client_memberships;
CREATE POLICY user_memberships_admin_manage ON public.user_client_memberships
    FOR ALL
    USING (
        client_id = public.get_current_client_id()
        AND EXISTS (
            SELECT 1
            FROM public.user_client_memberships ucm
            WHERE ucm.user_id = auth.uid()
              AND ucm.client_id = public.get_current_client_id()
              AND ucm.role = 'admin'
        )
    )
    WITH CHECK (
        client_id = public.get_current_client_id()
        AND EXISTS (
            SELECT 1
            FROM public.user_client_memberships ucm
            WHERE ucm.user_id = auth.uid()
              AND ucm.client_id = public.get_current_client_id()
              AND ucm.role = 'admin'
        )
    );

-- Service role full access
DROP POLICY IF EXISTS service_role_user_client_memberships ON public.user_client_memberships;
CREATE POLICY service_role_user_client_memberships ON public.user_client_memberships
    TO service_role
    USING (true) WITH CHECK (true);
