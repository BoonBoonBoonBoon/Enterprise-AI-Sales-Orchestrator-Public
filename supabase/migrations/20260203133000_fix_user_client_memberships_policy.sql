-- Migration: Fix recursive RLS on user_client_memberships
-- Date: 2026-02-03
-- Purpose: Avoid recursion by using a SECURITY DEFINER helper

-- Helper: is client admin
CREATE OR REPLACE FUNCTION public.is_client_admin(p_user_id UUID, p_client_id UUID)
RETURNS BOOLEAN
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM public.user_client_memberships ucm
        WHERE ucm.user_id = p_user_id
          AND ucm.client_id = p_client_id
          AND ucm.role = 'admin'
    );
$$;

-- Replace policy with helper to avoid recursion
ALTER TABLE public.user_client_memberships ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS user_memberships_admin_manage ON public.user_client_memberships;
CREATE POLICY user_memberships_admin_manage ON public.user_client_memberships
    FOR ALL
    USING (
        client_id = public.get_current_client_id()
        AND public.is_client_admin(auth.uid(), public.get_current_client_id())
    )
    WITH CHECK (
        client_id = public.get_current_client_id()
        AND public.is_client_admin(auth.uid(), public.get_current_client_id())
    );
