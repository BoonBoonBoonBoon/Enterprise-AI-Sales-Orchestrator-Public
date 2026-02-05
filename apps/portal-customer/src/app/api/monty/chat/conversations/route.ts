import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import { createServerClient } from '@supabase/ssr';
import { cookies } from 'next/headers';

export const dynamic = 'force-dynamic';

// Maximum number of conversations per user per lead
const MAX_CONVERSATIONS_PER_LEAD = 5;

function createAuthClient() {
  const cookieStore = cookies();
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        get(name: string) {
          return cookieStore.get(name)?.value;
        },
        set() {},
        remove() {},
      },
    }
  );
}

function createServiceClient() {
  return createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!,
    { auth: { persistSession: false, autoRefreshToken: false } }
  );
}

async function getClientIdForUser(supabase: any, userId: string): Promise<string | null> {
  const { data, error } = await supabase
    .from('user_client_memberships')
    .select('client_id')
    .eq('user_id', userId)
    .limit(1);

  if (!error && data && data.length > 0) {
    return data[0].client_id;
  }

  const devOverride = process.env.DEV_CLIENT_ID_OVERRIDE;
  if (process.env.NODE_ENV !== 'production' && devOverride) {
    return devOverride;
  }

  return null;
}

async function verifyLeadAccess(
  serviceSupabase: any,
  leadId: string,
  leadSource: 'leads' | 'staging_leads',
  clientId: string
): Promise<boolean> {
  const table = leadSource === 'leads' ? 'leads' : 'staging_leads';
  const { data, error } = await serviceSupabase
    .from(table)
    .select('id')
    .eq('id', leadId)
    .eq('client_id', clientId)
    .maybeSingle();

  if (error) return false;
  return Boolean(data?.id);
}

export async function GET(req: NextRequest) {
  try {
    const authClient = createAuthClient();
    const { data: { user }, error: authError } = await authClient.auth.getUser();

    if (authError || !user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const url = new URL(req.url);
    const leadId = url.searchParams.get('leadId');
    const leadSource = url.searchParams.get('leadSource');
    const limit = parseInt(url.searchParams.get('limit') || '20', 10);

    if (!leadId) return NextResponse.json({ error: 'leadId is required' }, { status: 400 });
    if (!leadSource || !['leads', 'staging_leads'].includes(leadSource)) {
      return NextResponse.json({ error: 'leadSource is required (leads|staging_leads)' }, { status: 400 });
    }

    const clientId = await getClientIdForUser(authClient, user.id);
    if (!clientId) return NextResponse.json({ error: 'User not associated with any client' }, { status: 403 });

    const leadClient = process.env.SUPABASE_SERVICE_ROLE_KEY ? createServiceClient() : authClient;
    const canAccessLead = await verifyLeadAccess(leadClient, leadId, leadSource as 'leads' | 'staging_leads', clientId);
    if (!canAccessLead) {
      return NextResponse.json({ error: 'Lead not found or access denied' }, { status: 404 });
    }

    let conversations: Array<{ id: string; status: string; created_at: string; ended_at: string | null; title: string | null; message_count: number }> = [];
    try {
      const { data, error } = await authClient
        .from('monty_chat_conversations')
        .select('id, status, created_at, ended_at, title, message_count')
        .eq('user_id', user.id)
        .eq('client_id', clientId)
        .eq('lead_id', leadId)
        .eq('lead_source', leadSource)
        .order('created_at', { ascending: false })
        .limit(MAX_CONVERSATIONS_PER_LEAD);

      if (error) {
        console.error('Error fetching chat conversations:', error);
      } else if (data) {
        conversations = data;
      }
    } catch (err) {
      console.warn('Monty conversations lookup skipped:', err);
    }

    // Include legacy (pre-conversation_id) messages as a closed conversation
    const { data: legacyMessages, error: legacyError } = await authClient
      .from('monty_chats')
      .select('id, created_at')
      .eq('user_id', user.id)
      .eq('client_id', clientId)
      .eq('lead_id', leadId)
      .eq('lead_source', leadSource)
      .is('conversation_id', null)
      .order('created_at', { ascending: true })
      .limit(1);

    if (legacyError) {
      console.warn('Legacy monty chat lookup failed:', legacyError);
    }

    const legacyConversation = legacyMessages && legacyMessages.length > 0
      ? {
          id: 'legacy',
          status: 'closed',
          created_at: legacyMessages[0].created_at,
          ended_at: legacyMessages[0].created_at,
          is_legacy: true,
        }
      : null;

    return NextResponse.json({
      conversations: legacyConversation
        ? [legacyConversation, ...conversations]
        : conversations,
    });

  } catch (error) {
    console.error('Get chat conversations error:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}

export async function POST(req: NextRequest) {
  try {
    const authClient = createAuthClient();
    const { data: { user }, error: authError } = await authClient.auth.getUser();

    if (authError || !user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    let body: { leadId: string; leadSource: 'leads' | 'staging_leads' };
    try {
      body = await req.json();
    } catch {
      return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
    }

    const { leadId, leadSource } = body;

    if (!leadId || typeof leadId !== 'string') {
      return NextResponse.json({ error: 'Missing or invalid leadId' }, { status: 400 });
    }

    if (!leadSource || !['leads', 'staging_leads'].includes(leadSource)) {
      return NextResponse.json(
        { error: 'Invalid leadSource. Must be "leads" or "staging_leads"' },
        { status: 400 }
      );
    }

    const clientId = await getClientIdForUser(authClient, user.id);
    if (!clientId) {
      return NextResponse.json({ error: 'User not associated with any client' }, { status: 403 });
    }

    const leadClient = process.env.SUPABASE_SERVICE_ROLE_KEY ? createServiceClient() : authClient;
    const canAccessLead = await verifyLeadAccess(leadClient, leadId, leadSource, clientId);
    if (!canAccessLead) {
      return NextResponse.json({ error: 'Lead not found or access denied' }, { status: 404 });
    }

    // Close any open conversations for this user/lead
    const now = new Date().toISOString();
    await authClient
      .from('monty_chat_conversations')
      .update({ status: 'closed', ended_at: now })
      .eq('user_id', user.id)
      .eq('client_id', clientId)
      .eq('lead_id', leadId)
      .eq('lead_source', leadSource)
      .eq('status', 'open');

    // Check how many conversations exist and delete oldest if over limit
    const { data: existingConversations, error: countError } = await authClient
      .from('monty_chat_conversations')
      .select('id, created_at')
      .eq('user_id', user.id)
      .eq('client_id', clientId)
      .eq('lead_id', leadId)
      .eq('lead_source', leadSource)
      .order('created_at', { ascending: false });

    if (!countError && existingConversations && existingConversations.length >= MAX_CONVERSATIONS_PER_LEAD) {
      // Delete oldest conversations (and their messages via CASCADE or manual delete)
      const toDelete = existingConversations.slice(MAX_CONVERSATIONS_PER_LEAD - 1);
      const idsToDelete = toDelete.map(c => c.id);
      
      // Delete associated messages first
      await authClient
        .from('monty_chats')
        .delete()
        .in('conversation_id', idsToDelete);
      
      // Delete the conversations
      await authClient
        .from('monty_chat_conversations')
        .delete()
        .in('id', idsToDelete);
    }

    // Create a new conversation
    const { data: conversation, error } = await authClient
      .from('monty_chat_conversations')
      .insert({
        user_id: user.id,
        client_id: clientId,
        lead_id: leadId,
        lead_source: leadSource,
        status: 'open',
      })
      .select('id, status, created_at, ended_at, title, message_count')
      .single();

    if (error || !conversation) {
      console.error('Error creating chat conversation:', error);
      return NextResponse.json({ error: 'Failed to start a new chat' }, { status: 500 });
    }

    return NextResponse.json({ conversation });

  } catch (error) {
    console.error('Start chat conversation error:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
