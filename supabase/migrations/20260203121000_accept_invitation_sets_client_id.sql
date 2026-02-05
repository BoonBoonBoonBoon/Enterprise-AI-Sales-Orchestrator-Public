-- Migration: Ensure invitation acceptance sets auth app_metadata client_id
-- Date: 2026-02-03
-- Purpose: Keep tenant context available via auth metadata (helps RLS + downstream sync)

CREATE OR REPLACE FUNCTION public.accept_invitation(
    p_invite_token TEXT,
    p_user_id UUID
) RETURNS JSONB
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path = public
    AS $$
DECLARE
    v_invitation RECORD;
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

    -- Create or update membership
    INSERT INTO public.user_client_memberships (user_id, client_id, role)
    VALUES (p_user_id, v_invitation.client_id, v_invitation.role)
    ON CONFLICT (user_id, client_id) DO UPDATE SET role = v_invitation.role;

    -- Mark invitation as accepted
    UPDATE public.pending_invitations
    SET accepted_at = now()
    WHERE id = v_invitation.id;

    -- Ensure auth app_metadata has client_id for tenant context
    UPDATE auth.users
    SET raw_app_meta_data = COALESCE(raw_app_meta_data, '{}'::jsonb) ||
        jsonb_build_object('client_id', v_invitation.client_id)
    WHERE id = p_user_id;

    -- Log the event
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
