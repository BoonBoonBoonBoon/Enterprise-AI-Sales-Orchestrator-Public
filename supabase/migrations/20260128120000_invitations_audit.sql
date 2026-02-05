-- Migration: Pending invitations and enhanced audit log
-- Date: 2026-01-28
-- Purpose: Support user invitation flow and comprehensive audit logging

-- ============================================================================
-- 1. PENDING INVITATIONS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.pending_invitations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES public.clients(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('admin', 'member', 'viewer')),
    invite_token TEXT NOT NULL UNIQUE,
    invited_by UUID NOT NULL,  -- References auth.users but no FK for flexibility
    name TEXT,
    expires_at TIMESTAMPTZ DEFAULT (now() + INTERVAL '7 days'),
    accepted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(client_id, email)  -- Only one pending invite per email per tenant
);

-- Index for token lookup during accept
CREATE INDEX IF NOT EXISTS idx_pending_invitations_token ON public.pending_invitations(invite_token);
CREATE INDEX IF NOT EXISTS idx_pending_invitations_email ON public.pending_invitations(email);
CREATE INDEX IF NOT EXISTS idx_pending_invitations_client_id ON public.pending_invitations(client_id);

-- RLS for pending invitations
ALTER TABLE public.pending_invitations ENABLE ROW LEVEL SECURITY;

-- Admins can see their tenant's invitations
DROP POLICY IF EXISTS "admin_manage_invitations" ON public.pending_invitations;
CREATE POLICY "admin_manage_invitations" ON public.pending_invitations
    FOR ALL
    USING (client_id = public.get_current_client_id());

-- Service role full access
DROP POLICY IF EXISTS "service_role_invitations" ON public.pending_invitations;
CREATE POLICY "service_role_invitations" ON public.pending_invitations
    TO service_role
    USING (true) WITH CHECK (true);

-- ============================================================================
-- 2. ENHANCED AUDIT LOG TABLE (if not exists or enhance)
-- ============================================================================
-- Note: audit_log uses 'user_or_agent' column, not 'actor_id'
-- We'll add the new columns for tracking

DO $$
BEGIN
    -- Add actor_email column if not exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' AND table_name = 'audit_log' AND column_name = 'actor_email'
    ) THEN
        ALTER TABLE public.audit_log ADD COLUMN actor_email TEXT;
    END IF;
    
    -- Add ip_address column if not exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' AND table_name = 'audit_log' AND column_name = 'ip_address'
    ) THEN
        ALTER TABLE public.audit_log ADD COLUMN ip_address TEXT;
    END IF;
    
    -- Add user_agent column if not exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' AND table_name = 'audit_log' AND column_name = 'user_agent'
    ) THEN
        ALTER TABLE public.audit_log ADD COLUMN user_agent TEXT;
    END IF;
    
    -- Add actor_id as alias column if not exists (for consistency with our code)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' AND table_name = 'audit_log' AND column_name = 'actor_id'
    ) THEN
        ALTER TABLE public.audit_log ADD COLUMN actor_id TEXT;
    END IF;
END $$;

-- Create indexes for audit log queries (only on existing columns)
CREATE INDEX IF NOT EXISTS idx_audit_log_client_id ON public.audit_log(client_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_user_or_agent ON public.audit_log(user_or_agent);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON public.audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON public.audit_log(created_at DESC);

-- ============================================================================
-- 3. FUNCTION TO ACCEPT INVITATION
-- ============================================================================
CREATE OR REPLACE FUNCTION public.accept_invitation(
    p_invite_token TEXT,
    p_user_id UUID
) RETURNS JSONB
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
DECLARE
    v_invitation RECORD;
    v_result JSONB;
BEGIN
    -- Find the invitation
    SELECT * INTO v_invitation
    FROM public.pending_invitations
    WHERE invite_token = p_invite_token
    AND accepted_at IS NULL
    AND expires_at > now();
    
    IF v_invitation IS NULL THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', 'Invalid or expired invitation'
        );
    END IF;
    
    -- Create membership
    INSERT INTO public.user_client_memberships (user_id, client_id, role)
    VALUES (p_user_id, v_invitation.client_id, v_invitation.role)
    ON CONFLICT (user_id, client_id) DO UPDATE SET role = v_invitation.role;
    
    -- Mark invitation as accepted
    UPDATE public.pending_invitations
    SET accepted_at = now()
    WHERE id = v_invitation.id;
    
    -- Log the event (using existing schema columns)
    INSERT INTO public.audit_log (client_id, action, user_or_agent, target_table, target_id, metadata, actor_id)
    VALUES (
        v_invitation.client_id,
        'invitation.accepted',
        p_user_id::TEXT,
        'pending_invitations',
        v_invitation.id,
        jsonb_build_object('email', v_invitation.email, 'role', v_invitation.role),
        p_user_id::TEXT
    );
    
    RETURN jsonb_build_object(
        'success', true,
        'client_id', v_invitation.client_id,
        'role', v_invitation.role
    );
END;
$$;

-- ============================================================================
-- 4. FUNCTION TO CREATE CLIENT ON SIGNUP (for self-serve)
-- ============================================================================
CREATE OR REPLACE FUNCTION public.create_client_on_signup()
RETURNS TRIGGER
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
DECLARE
    v_client_id UUID;
    v_company_name TEXT;
BEGIN
    -- Only run for new users without an existing client
    IF NEW.raw_app_meta_data ? 'client_id' THEN
        RETURN NEW;
    END IF;
    
    -- Get company name from user metadata or email domain
    v_company_name := COALESCE(
        NEW.raw_user_meta_data->>'company',
        split_part(NEW.email, '@', 2)
    );
    
    -- Create a new client
    INSERT INTO public.clients (name, domain)
    VALUES (v_company_name, split_part(NEW.email, '@', 2))
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

-- Note: The trigger on auth.users needs to be created via Supabase dashboard
-- or using Supabase's auth hooks, as we can't directly modify auth schema triggers
-- via regular migrations. Document this for manual setup:
-- 
-- CREATE TRIGGER on_auth_user_created
--   AFTER INSERT ON auth.users
--   FOR EACH ROW EXECUTE FUNCTION public.create_client_on_signup();

-- ============================================================================
-- 5. GRANT PERMISSIONS
-- ============================================================================
GRANT SELECT, INSERT, UPDATE, DELETE ON public.pending_invitations TO authenticated;
GRANT ALL ON public.pending_invitations TO service_role;
GRANT EXECUTE ON FUNCTION public.accept_invitation(TEXT, UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION public.accept_invitation(TEXT, UUID) TO service_role;
