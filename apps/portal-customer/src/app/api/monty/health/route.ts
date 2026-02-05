import { NextResponse } from 'next/server';
import { createServerClient } from '@supabase/ssr';
import { cookies } from 'next/headers';

export const dynamic = 'force-dynamic';

type HealthResponse = {
  ok: boolean;
  reasons: string[];
};

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

export async function GET() {
  const reasons: string[] = [];

  if (!process.env.NEXT_PUBLIC_SUPABASE_URL) {
    reasons.push('Missing NEXT_PUBLIC_SUPABASE_URL');
  }
  if (!process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY) {
    reasons.push('Missing NEXT_PUBLIC_SUPABASE_ANON_KEY');
  }
  if (!process.env.OPENAI_API_KEY && !process.env.ANTHROPIC_API_KEY) {
    reasons.push('Missing OPENAI_API_KEY or ANTHROPIC_API_KEY');
  }

  if (reasons.length === 0) {
    try {
      const authClient = createAuthClient();
      const { data: { user }, error: authError } = await authClient.auth.getUser();
      if (authError || !user) {
        reasons.push('Unauthorized (no active session)');
      } else {
        const clientId = await getClientIdForUser(authClient, user.id);
        if (!clientId) {
          reasons.push('User not linked to a client');
        }
      }
    } catch (err) {
      reasons.push('Supabase auth check failed');
    }
  }

  const payload: HealthResponse = {
    ok: reasons.length === 0,
    reasons,
  };

  return NextResponse.json(payload, { status: payload.ok ? 200 : 503 });
}
