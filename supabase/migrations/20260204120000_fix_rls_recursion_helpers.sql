-- Migration: Harden RLS helper functions to avoid recursion
-- Date: 2026-02-04
-- Purpose: Ensure SECURITY DEFINER helpers bypass RLS and update dependent policies

-- =============================================================================
-- 1. Replace is_client_admin with row_security disabled
-- =============================================================================
CREATE OR REPLACE FUNCTION public.is_client_admin(p_user_id UUID, p_client_id UUID)
RETURNS BOOLEAN
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    PERFORM set_config('row_security', 'off', true);

    RETURN EXISTS (
        SELECT 1
        FROM public.user_client_memberships ucm
        WHERE ucm.user_id = p_user_id
          AND ucm.client_id = p_client_id
          AND ucm.role = 'admin'
    );
END;
$$;

-- =============================================================================
-- 2. Replace get_client_id_for_user with row_security disabled
-- =============================================================================
CREATE OR REPLACE FUNCTION public.get_client_id_for_user(p_user_id UUID)
RETURNS UUID
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_client_id UUID;
BEGIN
    PERFORM set_config('row_security', 'off', true);

    SELECT ucm.client_id
    INTO v_client_id
    FROM public.user_client_memberships ucm
    WHERE ucm.user_id = p_user_id
    ORDER BY ucm.client_id
    LIMIT 1;

    RETURN v_client_id;
END;
$$;

-- =============================================================================
-- 3. Update user_profiles tenant admin policy to use helper
-- =============================================================================
ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS user_profiles_tenant_admin_read ON public.user_profiles;
CREATE POLICY user_profiles_tenant_admin_read ON public.user_profiles
    FOR SELECT
    USING (
        client_id = public.get_current_client_id()
        AND public.is_client_admin(auth.uid(), public.get_current_client_id())
    );
