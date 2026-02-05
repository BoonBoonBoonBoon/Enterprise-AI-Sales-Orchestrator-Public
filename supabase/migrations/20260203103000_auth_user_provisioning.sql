-- Migration: Auto-provision client + membership on auth signup, sync on updates
-- Date: 2026-02-03
-- Purpose: Connect users to clients on signup and keep client profile updated

-- ============================================================================
-- 1. Update create_client_on_signup to store richer client data
-- ============================================================================
CREATE OR REPLACE FUNCTION public.create_client_on_signup()
RETURNS TRIGGER
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path = public
    AS $$
DECLARE
    v_client_id UUID;
    v_company_name TEXT;
    v_domain TEXT;
BEGIN
    -- Only run for new users without an existing client
    IF NEW.raw_app_meta_data ? 'client_id' THEN
        RETURN NEW;
    END IF;

    v_domain := split_part(NEW.email, '@', 2);
    v_company_name := COALESCE(
        NULLIF(NEW.raw_user_meta_data->>'company', ''),
        v_domain
    );

    -- Create a new client
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
        NULLIF(NEW.raw_user_meta_data->>'full_name', ''),
        NEW.email,
        NULLIF(NEW.raw_user_meta_data->>'phone', ''),
        NULLIF(NEW.raw_user_meta_data->>'billing_email', ''),
        NULLIF(NEW.raw_user_meta_data->>'support_email', '')
    )
    RETURNING id INTO v_client_id;

    -- Create owner membership
    INSERT INTO public.user_client_memberships (user_id, client_id, role)
    VALUES (NEW.id, v_client_id, 'admin');

    -- Update user's app_metadata with client_id
    NEW.raw_app_meta_data := COALESCE(NEW.raw_app_meta_data, '{}'::jsonb) ||
        jsonb_build_object('client_id', v_client_id);

    -- Log the event (using existing schema columns)
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

-- ============================================================================
-- 2. Sync client record when account updates
-- ============================================================================
CREATE OR REPLACE FUNCTION public.sync_client_on_user_update()
RETURNS TRIGGER
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path = public
    AS $$
DECLARE
    v_client_id UUID;
    v_is_admin BOOLEAN;
BEGIN
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

    UPDATE public.clients
    SET
        name = COALESCE(NULLIF(NEW.raw_user_meta_data->>'company', ''), name),
        email = COALESCE(NEW.email, email),
        domain = COALESCE(split_part(NEW.email, '@', 2), domain),
        primary_contact_name = COALESCE(NULLIF(NEW.raw_user_meta_data->>'full_name', ''), primary_contact_name),
        primary_contact_email = COALESCE(NEW.email, primary_contact_email),
        primary_contact_phone = COALESCE(NULLIF(NEW.raw_user_meta_data->>'phone', ''), primary_contact_phone),
        billing_email = COALESCE(NULLIF(NEW.raw_user_meta_data->>'billing_email', ''), billing_email),
        support_email = COALESCE(NULLIF(NEW.raw_user_meta_data->>'support_email', ''), support_email),
        updated_at = now()
    WHERE id = v_client_id;

    RETURN NEW;
END;
$$;

-- ============================================================================
-- 3. Auth triggers
-- ============================================================================
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    BEFORE INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.create_client_on_signup();

DROP TRIGGER IF EXISTS on_auth_user_updated ON auth.users;
CREATE TRIGGER on_auth_user_updated
    AFTER UPDATE ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.sync_client_on_user_update();
