-- Migration: User profiles + consistent personal info storage on signup/update
-- Date: 2026-02-03
-- Purpose: Persist user personal info (name/email/phone) in a dedicated table, keep synced from auth.users

-- =============================================================================
-- 1. user_profiles table
-- =============================================================================
CREATE TABLE IF NOT EXISTS public.user_profiles (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    client_id UUID REFERENCES public.clients(id) ON DELETE SET NULL,
    email TEXT,
    full_name TEXT,
    phone TEXT,
    avatar_url TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_user_profiles_client_id ON public.user_profiles(client_id);
CREATE INDEX IF NOT EXISTS idx_user_profiles_email ON public.user_profiles(email);

DROP TRIGGER IF EXISTS update_user_profiles_updated_at ON public.user_profiles;
CREATE TRIGGER update_user_profiles_updated_at
    BEFORE UPDATE ON public.user_profiles
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY;

-- Users can read/update their own profile
DROP POLICY IF EXISTS user_profiles_self ON public.user_profiles;
CREATE POLICY user_profiles_self ON public.user_profiles
    FOR ALL
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

-- Tenant admins can read profiles for the current client
DROP POLICY IF EXISTS user_profiles_tenant_admin_read ON public.user_profiles;
CREATE POLICY user_profiles_tenant_admin_read ON public.user_profiles
    FOR SELECT
    USING (
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
DROP POLICY IF EXISTS service_role_user_profiles ON public.user_profiles;
CREATE POLICY service_role_user_profiles ON public.user_profiles
    TO service_role
    USING (true) WITH CHECK (true);

-- =============================================================================
-- 2. Upsert profile from auth.users (runs on insert/update)
-- =============================================================================
CREATE OR REPLACE FUNCTION public.upsert_user_profile_from_auth()
RETURNS TRIGGER
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path = public
    AS $$
DECLARE
    v_client_id UUID;
    v_full_name TEXT;
BEGIN
    -- Bypass RLS for provisioning
    PERFORM set_config('row_security', 'off', true);

    v_client_id := COALESCE(
        NULLIF((NEW.raw_app_meta_data->>'client_id'), '')::uuid,
        NULLIF((NEW.raw_app_meta_data->>'tenant_id'), '')::uuid
    );

    v_full_name := COALESCE(
        NULLIF(NEW.raw_user_meta_data->>'full_name', ''),
        NULLIF(NEW.raw_user_meta_data->>'name', ''),
        NULLIF(NEW.raw_user_meta_data->>'display_name', '')
    );

    INSERT INTO public.user_profiles (
        user_id,
        client_id,
        email,
        full_name,
        phone,
        avatar_url,
        metadata
    )
    VALUES (
        NEW.id,
        v_client_id,
        NEW.email,
        v_full_name,
        NULLIF(NEW.raw_user_meta_data->>'phone', ''),
        NULLIF(NEW.raw_user_meta_data->>'avatar_url', ''),
        COALESCE(NEW.raw_user_meta_data, '{}'::jsonb)
    )
    ON CONFLICT (user_id) DO UPDATE SET
        client_id = COALESCE(EXCLUDED.client_id, public.user_profiles.client_id),
        email = COALESCE(EXCLUDED.email, public.user_profiles.email),
        full_name = COALESCE(EXCLUDED.full_name, public.user_profiles.full_name),
        phone = COALESCE(EXCLUDED.phone, public.user_profiles.phone),
        avatar_url = COALESCE(EXCLUDED.avatar_url, public.user_profiles.avatar_url),
        metadata = COALESCE(EXCLUDED.metadata, public.user_profiles.metadata),
        updated_at = now();

    RETURN NEW;
END;
$$;

-- Triggers for profile upsert
DROP TRIGGER IF EXISTS on_auth_user_created_profile ON auth.users;
CREATE TRIGGER on_auth_user_created_profile
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.upsert_user_profile_from_auth();

DROP TRIGGER IF EXISTS on_auth_user_updated_profile ON auth.users;
CREATE TRIGGER on_auth_user_updated_profile
    AFTER UPDATE ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.upsert_user_profile_from_auth();

-- =============================================================================
-- 3. Keep client/contact sync aligned with portal signup metadata keys
--    Portal sends: options.data = { name }
-- =============================================================================
CREATE OR REPLACE FUNCTION public.create_client_on_signup()
RETURNS TRIGGER
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path = public
    AS $$
DECLARE
    v_client_id UUID;
    v_company_name TEXT;
    v_domain TEXT;
    v_contact_name TEXT;
BEGIN
    PERFORM set_config('row_security', 'off', true);

    IF NEW.raw_app_meta_data ? 'client_id' THEN
        RETURN NEW;
    END IF;

    v_domain := split_part(NEW.email, '@', 2);
    v_company_name := COALESCE(
        NULLIF(NEW.raw_user_meta_data->>'company', ''),
        v_domain
    );

    v_contact_name := COALESCE(
        NULLIF(NEW.raw_user_meta_data->>'full_name', ''),
        NULLIF(NEW.raw_user_meta_data->>'name', ''),
        NULLIF(NEW.raw_user_meta_data->>'display_name', '')
    );

    INSERT INTO public.clients (
        name,
        domain,
        email,
        primary_contact_name,
        primary_contact_email,
        primary_contact_phone,
        billing_email,
        support_email
    )
    VALUES (
        v_company_name,
        v_domain,
        NEW.email,
        v_contact_name,
        NEW.email,
        NULLIF(NEW.raw_user_meta_data->>'phone', ''),
        NULLIF(NEW.raw_user_meta_data->>'billing_email', ''),
        NULLIF(NEW.raw_user_meta_data->>'support_email', '')
    )
    RETURNING id INTO v_client_id;

    INSERT INTO public.user_client_memberships (user_id, client_id, role)
    VALUES (NEW.id, v_client_id, 'admin');

    NEW.raw_app_meta_data := COALESCE(NEW.raw_app_meta_data, '{}'::jsonb) ||
        jsonb_build_object('client_id', v_client_id);

    INSERT INTO public.audit_log (client_id, action, user_or_agent, target_table, metadata, actor_id)
    VALUES (
        v_client_id,
        'client.created',
        NEW.id::TEXT,
        'clients',
        jsonb_build_object('email', NEW.email, 'company', v_company_name),
        NEW.id::TEXT
    );

    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.sync_client_on_user_update()
RETURNS TRIGGER
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path = public
    AS $$
DECLARE
    v_client_id UUID;
    v_is_admin BOOLEAN;
    v_contact_name TEXT;
BEGIN
    PERFORM set_config('row_security', 'off', true);

    v_client_id := COALESCE(
        NULLIF((NEW.raw_app_meta_data->>'client_id'), '')::uuid,
        NULLIF((NEW.raw_app_meta_data->>'tenant_id'), '')::uuid
    );

    IF v_client_id IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM public.user_client_memberships ucm
        WHERE ucm.user_id = NEW.id
          AND ucm.client_id = v_client_id
          AND ucm.role = 'admin'
    ) INTO v_is_admin;

    IF NOT v_is_admin THEN
        RETURN NEW;
    END IF;

    v_contact_name := COALESCE(
        NULLIF(NEW.raw_user_meta_data->>'full_name', ''),
        NULLIF(NEW.raw_user_meta_data->>'name', ''),
        NULLIF(NEW.raw_user_meta_data->>'display_name', '')
    );

    UPDATE public.clients
    SET
        name = COALESCE(NULLIF(NEW.raw_user_meta_data->>'company', ''), name),
        email = COALESCE(NEW.email, email),
        domain = COALESCE(split_part(NEW.email, '@', 2), domain),
        primary_contact_name = COALESCE(v_contact_name, primary_contact_name),
        primary_contact_email = COALESCE(NEW.email, primary_contact_email),
        primary_contact_phone = COALESCE(NULLIF(NEW.raw_user_meta_data->>'phone', ''), primary_contact_phone),
        billing_email = COALESCE(NULLIF(NEW.raw_user_meta_data->>'billing_email', ''), billing_email),
        support_email = COALESCE(NULLIF(NEW.raw_user_meta_data->>'support_email', ''), support_email),
        updated_at = now()
    WHERE id = v_client_id;

    RETURN NEW;
END;
$$;
