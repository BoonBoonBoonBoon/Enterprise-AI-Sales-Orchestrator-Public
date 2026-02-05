-- Migration: Expand clients profile + tighten RLS
-- Date: 2026-02-03
-- Purpose: Add descriptive client fields for portal usage and enforce tenant-aware RLS

-- =============================================================================
-- 1. Expand clients table with descriptive fields
-- =============================================================================
ALTER TABLE public.clients
    ADD COLUMN IF NOT EXISTS email TEXT,
    ADD COLUMN IF NOT EXISTS legal_name TEXT,
    ADD COLUMN IF NOT EXISTS domain TEXT,
    ADD COLUMN IF NOT EXISTS website_url TEXT,
    ADD COLUMN IF NOT EXISTS industry TEXT,
    ADD COLUMN IF NOT EXISTS company_size TEXT,
    ADD COLUMN IF NOT EXISTS timezone TEXT DEFAULT 'UTC',
    ADD COLUMN IF NOT EXISTS locale TEXT DEFAULT 'en-US',
    ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'active',
    ADD COLUMN IF NOT EXISTS plan TEXT DEFAULT 'standard',
    ADD COLUMN IF NOT EXISTS billing_status TEXT DEFAULT 'active',
    ADD COLUMN IF NOT EXISTS billing_email TEXT,
    ADD COLUMN IF NOT EXISTS support_email TEXT,
    ADD COLUMN IF NOT EXISTS phone TEXT,
    ADD COLUMN IF NOT EXISTS address_line1 TEXT,
    ADD COLUMN IF NOT EXISTS address_line2 TEXT,
    ADD COLUMN IF NOT EXISTS city TEXT,
    ADD COLUMN IF NOT EXISTS state TEXT,
    ADD COLUMN IF NOT EXISTS postal_code TEXT,
    ADD COLUMN IF NOT EXISTS country TEXT,
    ADD COLUMN IF NOT EXISTS primary_contact_name TEXT,
    ADD COLUMN IF NOT EXISTS primary_contact_title TEXT,
    ADD COLUMN IF NOT EXISTS primary_contact_email TEXT,
    ADD COLUMN IF NOT EXISTS primary_contact_phone TEXT,
    ADD COLUMN IF NOT EXISTS settings JSONB DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS portal_settings JSONB DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS features JSONB DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS stripe_customer_id TEXT,
    ADD COLUMN IF NOT EXISTS subscribed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS trial_ends_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS canceled_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS onboarding_status TEXT DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS onboarding_completed_at TIMESTAMPTZ;

-- Optional status checks (keep defaults compatible)
ALTER TABLE public.clients
    DROP CONSTRAINT IF EXISTS clients_status_check,
    ADD CONSTRAINT clients_status_check CHECK (status IN ('active', 'inactive', 'suspended'));

ALTER TABLE public.clients
    DROP CONSTRAINT IF EXISTS clients_billing_status_check,
    ADD CONSTRAINT clients_billing_status_check CHECK (billing_status IN ('active', 'past_due', 'trialing', 'canceled'));

ALTER TABLE public.clients
    DROP CONSTRAINT IF EXISTS clients_onboarding_status_check,
    ADD CONSTRAINT clients_onboarding_status_check CHECK (onboarding_status IN ('pending', 'in_progress', 'completed'));

-- Useful indexes for lookups
CREATE INDEX IF NOT EXISTS idx_clients_domain ON public.clients(domain);
CREATE INDEX IF NOT EXISTS idx_clients_status ON public.clients(status);
CREATE INDEX IF NOT EXISTS idx_clients_plan ON public.clients(plan);

-- =============================================================================
-- 2. Ensure membership table exists (required for RLS resolution)
-- =============================================================================
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

-- =============================================================================
-- 3. Tenant resolution helper
-- =============================================================================
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

-- =============================================================================
-- 4. RLS policies for clients (tenant-aware)
-- =============================================================================
ALTER TABLE public.clients ENABLE ROW LEVEL SECURITY;

-- Remove legacy agent-only policies if they exist
DROP POLICY IF EXISTS clients_agent_select ON public.clients;
DROP POLICY IF EXISTS clients_agent_write ON public.clients;

-- Tenant-aware policy + agent bypass (read)
DROP POLICY IF EXISTS clients_tenant_access ON public.clients;
CREATE POLICY clients_tenant_access ON public.clients
    FOR ALL
    USING (
        id = public.get_current_client_id()
        OR public.get_user_role() IN ('agent_reader', 'agent_writer')
    )
    WITH CHECK (
        id = public.get_current_client_id()
        OR public.get_user_role() = 'agent_writer'
    );

-- Service role full access
DROP POLICY IF EXISTS service_role_clients ON public.clients;
CREATE POLICY service_role_clients ON public.clients
    TO service_role
    USING (true) WITH CHECK (true);
