import { NextResponse, type NextRequest } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import { createClient as createServerSupabaseClient } from '@/lib/supabase/server';

export const dynamic = 'force-dynamic';

type Dataset = 'staging' | 'qualified';

function isDataset(value: string | null): value is Dataset {
  return value === 'staging' || value === 'qualified';
}

export async function GET(req: Request) {
  const url = new URL(req.url);
  const datasetParam = url.searchParams.get('dataset');

  if (!isDataset(datasetParam)) {
    return NextResponse.json({ error: "Missing or invalid 'dataset' (use 'staging' or 'qualified')" }, { status: 400 });
  }

  // Require an authenticated user so we can scope results to a single tenant.
  // Use the shared server client helper so auth cookies are read/rotated correctly.
  const authClient = createServerSupabaseClient();

  const { data: { user }, error: authError } = await authClient.auth.getUser();
  if (authError || !user) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  // Resolve tenant client_id via membership.
  // If you don't yet have a membership row in dev, you can set DEV_CLIENT_ID_OVERRIDE.
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
    const details = membershipError ? ` (${membershipError.message})` : '';
    return NextResponse.json(
      { error: `User not associated with any client${details}. In dev, set DEV_CLIENT_ID_OVERRIDE to a client UUID.` },
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

  const supabase = createClient(supabaseUrl, serviceRoleKey, {
    auth: { persistSession: false, autoRefreshToken: false },
  });

  const table = datasetParam === 'staging' ? 'staging_leads' : 'leads';

  const { data, error } = await supabase
    .from(table)
    .select('*')
    .eq('client_id', clientId)
    .order('created_at', { ascending: false });

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  // For qualified leads, also fetch their conversations
  let conversationsMap: Record<string, any[]> = {};
  if (datasetParam === 'qualified' && data && data.length > 0) {
    const leadIds = data.map((l: any) => l.id);
    const { data: convos } = await supabase
      .from('conversations')
      .select('id, lead_id, channel, status, summary, subject, created_at, updated_at')
      .in('lead_id', leadIds)
      .order('updated_at', { ascending: false });

    if (convos) {
      for (const c of convos) {
        if (!conversationsMap[c.lead_id]) {
          conversationsMap[c.lead_id] = [];
        }
        conversationsMap[c.lead_id].push(c);
      }
    }
  }

  // For staging leads, fetch staging_conversations
  if (datasetParam === 'staging' && data && data.length > 0) {
    const stagingLeadIds = data.map((l: any) => l.id);
    const { data: stagingConvos } = await supabase
      .from('staging_conversations')
      .select('id, staging_lead_id, channel, status, subject, created_at, updated_at')
      .in('staging_lead_id', stagingLeadIds)
      .order('updated_at', { ascending: false });

    if (stagingConvos) {
      for (const c of stagingConvos) {
        if (!conversationsMap[c.staging_lead_id]) {
          conversationsMap[c.staging_lead_id] = [];
        }
        conversationsMap[c.staging_lead_id].push({
          ...c,
          lead_id: c.staging_lead_id, // normalize field name
        });
      }
    }
  }

  return NextResponse.json({ data: data ?? [], conversations: conversationsMap });
}
