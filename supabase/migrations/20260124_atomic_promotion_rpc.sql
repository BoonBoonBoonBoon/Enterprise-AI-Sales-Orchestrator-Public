-- Migration: Atomic Promotion RPC (staging -> leads)
-- Date: 2026-01-24
-- Purpose: Perform atomic, idempotent promotion of staging leads into production tables.

CREATE OR REPLACE FUNCTION public.promote_staging_lead_atomic(
    p_staging_lead_id uuid,
    p_lead_id uuid
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_now timestamptz := now();
    v_client_id uuid;
    v_copied_conversations int := 0;
    v_copied_messages int := 0;
    v_conv_id uuid;
    v_sc record;
    v_sm record;
BEGIN
    SELECT client_id
    INTO v_client_id
    FROM public.staging_leads
    WHERE id = p_staging_lead_id
      AND archived_at IS NULL
    FOR UPDATE;

    IF v_client_id IS NULL THEN
        RETURN jsonb_build_object(
            'ok', false,
            'error', 'staging_lead_not_found',
            'staging_lead_id', p_staging_lead_id
        );
    END IF;

    FOR v_sc IN
        SELECT *
        FROM public.staging_conversations
        WHERE staging_lead_id = p_staging_lead_id
          AND archived_at IS NULL
        FOR UPDATE
    LOOP
        v_conv_id := uuid_generate_v5(
            '00000000-0000-0000-0000-000000000000',
            p_lead_id::text || ':' || COALESCE(v_sc.thread_id, v_sc.subject, 'conversation')
        );

        INSERT INTO public.conversations (
            id,
            client_id,
            lead_id,
            channel,
            status,
            summary,
            thread_id,
            subject,
            created_at,
            updated_at
        ) VALUES (
            v_conv_id,
            v_client_id,
            p_lead_id,
            COALESCE(v_sc.channel, 'email'),
            COALESCE(v_sc.status, 'active'),
            COALESCE(v_sc.summary, v_sc.subject, ''),
            v_sc.thread_id,
            v_sc.subject,
            v_now,
            v_now
        )
        ON CONFLICT (id) DO UPDATE SET
            client_id = EXCLUDED.client_id,
            lead_id = EXCLUDED.lead_id,
            channel = EXCLUDED.channel,
            status = EXCLUDED.status,
            summary = EXCLUDED.summary,
            thread_id = EXCLUDED.thread_id,
            subject = EXCLUDED.subject,
            updated_at = v_now;

        v_copied_conversations := v_copied_conversations + 1;

        FOR v_sm IN
            SELECT *
            FROM public.staging_messages
            WHERE staging_conversation_id = v_sc.id
              AND archived_at IS NULL
            FOR UPDATE
        LOOP
            INSERT INTO public.messages (
                id,
                conversation_id,
                sender_type,
                text_content,
                metadata,
                sent_at,
                message_id,
                created_at
            ) VALUES (
                uuid_generate_v5(
                    '00000000-0000-0000-0000-000000000000',
                    v_conv_id::text || ':' || COALESCE(v_sm.message_id, v_sm.id::text)
                ),
                v_conv_id,
                COALESCE(v_sm.direction, 'inbound'),
                COALESCE(v_sm.content, ''),
                COALESCE(v_sm.metadata::text, '{}'),
                COALESCE(v_sm.sent_at::text, v_now::text),
                v_sm.message_id,
                v_now
            )
            ON CONFLICT (id) DO NOTHING;

            v_copied_messages := v_copied_messages + 1;

            UPDATE public.staging_messages
            SET archived_at = v_now,
                updated_at = v_now
            WHERE id = v_sm.id
              AND archived_at IS NULL;
        END LOOP;

        UPDATE public.staging_conversations
        SET archived_at = v_now,
            updated_at = v_now
        WHERE id = v_sc.id
          AND archived_at IS NULL;
    END LOOP;

    UPDATE public.staging_leads
    SET archived_at = v_now,
        updated_at = v_now,
        enrichment_status = 'promoted'
    WHERE id = p_staging_lead_id
      AND archived_at IS NULL;

    RETURN jsonb_build_object(
        'ok', true,
        'staging_lead_id', p_staging_lead_id,
        'lead_id', p_lead_id,
        'copied_conversations', v_copied_conversations,
        'copied_messages', v_copied_messages,
        'archived_at', v_now
    );
END;
$$;
