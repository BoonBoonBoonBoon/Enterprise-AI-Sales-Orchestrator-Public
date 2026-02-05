-- Migration: Tenant resolution helpers (for RLS)
-- Date: 2026-01-28
-- Purpose: Provide get_current_client_id before policies that depend on it

-- Ensure membership table exists for tenant resolution
CREATE TABLE IF NOT EXISTS public.user_client_memberships (
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    client_id UUID REFERENCES public.clients(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('admin', 'member', 'viewer')),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (user_id, client_id)
);

-- Updated_at trigger for memberships
DROP TRIGGER IF EXISTS update_user_client_memberships_updated_at ON public.user_client_memberships;
CREATE TRIGGER update_user_client_memberships_updated_at
    BEFORE UPDATE ON public.user_client_memberships
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();

-- Tenant resolution helper used by RLS policies
CREATE OR REPLACE FUNCTION public.get_current_client_id() RETURNS UUID
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path = public
    AS $$
    SELECT COALESCE(
        NULLIF(current_setting('app.current_client', true), '')::uuid,
        NULLIF((current_setting('request.jwt.claims', true)::jsonb ->> 'client_id'), '')::uuid,
        NULLIF((current_setting('request.jwt.claims', true)::jsonb ->> 'tenant_id'), '')::uuid,
        NULLIF((current_setting('request.headers', true)::jsonb ->> 'x-client-id'), '')::uuid,
        (
            SELECT ucm.client_id
            FROM public.user_client_memberships ucm
            WHERE ucm.user_id = auth.uid()
            ORDER BY ucm.client_id
            LIMIT 1
        )
    );
$$;
