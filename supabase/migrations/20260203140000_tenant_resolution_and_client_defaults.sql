-- Migration: Harden tenant resolution and default client_id on inserts
-- Date: 2026-02-03
-- Purpose: Avoid RLS recursion and ensure client-scoped rows are set correctly

-- Helper: fetch client_id for user without RLS recursion
CREATE OR REPLACE FUNCTION public.get_client_id_for_user(p_user_id UUID)
RETURNS UUID
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public
AS $$
    SELECT ucm.client_id
    FROM public.user_client_memberships ucm
    WHERE ucm.user_id = p_user_id
    ORDER BY ucm.client_id
    LIMIT 1;
$$;

-- Replace tenant resolver to use helper (avoids recursion on user_client_memberships policies)
CREATE OR REPLACE FUNCTION public.get_current_client_id() RETURNS UUID
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path = public
    AS $$
    SELECT COALESCE(
        NULLIF(current_setting('app.current_client', true), '')::uuid,
        NULLIF((current_setting('request.jwt.claims', true)::jsonb ->> 'client_id'), '')::uuid,
        NULLIF((current_setting('request.jwt.claims', true)::jsonb ->> 'tenant_id'), '')::uuid,
        NULLIF((current_setting('request.headers', true)::jsonb ->> 'x-client-id'), '')::uuid,
        public.get_client_id_for_user(auth.uid())
    );
$$;

-- Default client_id on insert for tenant-scoped tables
CREATE OR REPLACE FUNCTION public.set_client_id_from_current()
RETURNS TRIGGER
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    IF NEW.client_id IS NULL THEN
        NEW.client_id := public.get_current_client_id();
    END IF;
    RETURN NEW;
END;
$$;

-- Mailboxes: ensure client_id is set from current tenant
DROP TRIGGER IF EXISTS set_mailboxes_client_id ON public.mailboxes;
CREATE TRIGGER set_mailboxes_client_id
    BEFORE INSERT ON public.mailboxes
    FOR EACH ROW
    EXECUTE FUNCTION public.set_client_id_from_current();

-- Drafts: ensure client_id is set from current tenant
DROP TRIGGER IF EXISTS set_drafts_client_id ON public.drafts;
CREATE TRIGGER set_drafts_client_id
    BEFORE INSERT ON public.drafts
    FOR EACH ROW
    EXECUTE FUNCTION public.set_client_id_from_current();
