import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import { createClient as createServerSupabaseClient } from '@/lib/supabase/server';

export const dynamic = 'force-dynamic';

type Source = 'leads' | 'staging';

function isSource(value: string | null): value is Source {
  return value === 'leads' || value === 'staging';
}

export async function GET(req: Request) {
  const url = new URL(req.url);
  const conversationId = url.searchParams.get('conversationId');
  const sourceParam = url.searchParams.get('source');

  if (!conversationId) {
    return NextResponse.json({ error: 'conversationId is required' }, { status: 400 });
  }

  if (!isSource(sourceParam)) {
    return NextResponse.json({ error: 'source is required (leads|staging)' }, { status: 400 });
  }

  const authClient = createServerSupabaseClient();
  const { data: { user }, error: authError } = await authClient.auth.getUser();

  if (authError || !user) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  let clientId: string | null = null;
  const { data: membership, error: membershipError } = await authClient
    .from('user_client_memberships')
    .select('client_id')
    .eq('user_id', user.id)
    .limit(1);

  if (!membershipError && membership && membership.length > 0) {
    clientId = membership[0].client_id;
  }

  const devOverride = process.env.DEV_CLIENT_ID_OVERRIDE;
  if (!clientId && process.env.NODE_ENV !== 'production' && devOverride) {
    clientId = devOverride;
  }

  if (!clientId) {
    return NextResponse.json(
      { error: 'User not associated with any client' },
      { status: 403 }
    );
  }

  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

  if (!supabaseUrl || !serviceRoleKey) {
    return NextResponse.json(
      { error: 'Server is missing SUPABASE_SERVICE_ROLE_KEY or NEXT_PUBLIC_SUPABASE_URL' },
      { status: 500 }
    );
  }

  const serviceClient = createClient(supabaseUrl, serviceRoleKey, {
    auth: { persistSession: false, autoRefreshToken: false },
  });

  if (sourceParam === 'leads') {
    const { data: conversation, error: convoError } = await serviceClient
      .from('conversations')
      .select('id, lead_id')
      .eq('id', conversationId)
      .maybeSingle();

    if (convoError || !conversation?.id) {
      return NextResponse.json({ error: 'Conversation not found' }, { status: 404 });
    }

    const { data: lead } = await serviceClient
      .from('leads')
      .select('id')
      .eq('id', conversation.lead_id)
      .eq('client_id', clientId)
      .maybeSingle();

    if (!lead?.id) {
      return NextResponse.json({ error: 'Conversation not found' }, { status: 404 });
    }

    const { data: messages, error: msgError } = await serviceClient
      .from('messages')
      .select('id, sender_type, text_content, sent_at')
      .eq('conversation_id', conversationId)
      .order('sent_at', { ascending: true });

    if (msgError) {
      return NextResponse.json({ error: msgError.message }, { status: 500 });
    }

    const normalized = (messages ?? []).map((msg: { id: string; sender_type?: string; text_content: string; sent_at: string }) => ({
      id: msg.id,
      sender: msg.sender_type === 'agent' || msg.sender_type === 'lead' ? msg.sender_type : 'unknown',
      content: msg.text_content,
      sent_at: msg.sent_at,
    }));

    return NextResponse.json({ messages: normalized });
  }

  const { data: stagingConversation, error: stagingConvoError } = await serviceClient
    .from('staging_conversations')
    .select('id, staging_lead_id')
    .eq('id', conversationId)
    .maybeSingle();

  if (stagingConvoError || !stagingConversation?.id) {
    return NextResponse.json({ error: 'Conversation not found' }, { status: 404 });
  }

  const { data: stagingLead } = await serviceClient
    .from('staging_leads')
    .select('id')
    .eq('id', stagingConversation.staging_lead_id)
    .eq('client_id', clientId)
    .maybeSingle();

  if (!stagingLead?.id) {
    return NextResponse.json({ error: 'Conversation not found' }, { status: 404 });
  }

  const { data: stagingMessages, error: stagingMsgError } = await serviceClient
    .from('staging_messages')
    .select('id, sender, content, sent_at')
    .eq('staging_conversation_id', conversationId)
    .order('sent_at', { ascending: true });

  if (stagingMsgError) {
    return NextResponse.json({ error: stagingMsgError.message }, { status: 500 });
  }

  const normalized = (stagingMessages ?? []).map((msg: { id: string; sender?: string; content: string; sent_at: string }) => ({
    id: msg.id,
    sender: msg.sender === 'agent' || msg.sender === 'lead' ? msg.sender : 'unknown',
    content: msg.content,
    sent_at: msg.sent_at,
  }));

  return NextResponse.json({ messages: normalized });
}
