-- Migration: Fix auth signup trigger timing for FK integrity
-- Date: 2026-02-03
-- Purpose: Ensure auth.users exists before inserting membership (FK)

-- Replace signup provisioning function to run AFTER INSERT safely
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

    -- Only run for new users without an existing client
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

    -- Update user's app_metadata with client_id after insert
    UPDATE auth.users
    SET raw_app_meta_data = COALESCE(raw_app_meta_data, '{}'::jsonb) ||
        jsonb_build_object('client_id', v_client_id)
    WHERE id = NEW.id;

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

-- Ensure trigger is AFTER INSERT (not BEFORE) to satisfy FK
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.create_client_on_signup();
