import type { SupabaseClient } from '@supabase/supabase-js';

export interface CurrentProfile {
  userId: string;
  email: string | null;
  fullName: string | null;
  phone: string | null;
  clientId: string | null;
  clientName: string | null;
  clientDomain: string | null;
}

export async function getCurrentProfile(supabase: SupabaseClient): Promise<CurrentProfile | null> {
  const { data: userData, error: userError } = await supabase.auth.getUser();
  if (userError || !userData.user) {
    return null;
  }

  const user = userData.user;
  const { data: profile } = await supabase
    .from('user_profiles')
    .select('user_id, full_name, email, phone, client_id')
    .eq('user_id', user.id)
    .maybeSingle();

  const clientId =
    profile?.client_id ||
    (user.user_metadata as { client_id?: string } | undefined)?.client_id ||
    (user.app_metadata as { client_id?: string } | undefined)?.client_id ||
    null;

  const { data: client } = clientId
    ? await supabase
        .from('clients')
        .select('id, name, domain')
        .eq('id', clientId)
        .maybeSingle()
    : { data: null };

  return {
    userId: user.id,
    email: profile?.email ?? user.email ?? null,
    fullName:
      profile?.full_name ??
      (user.user_metadata as { name?: string } | undefined)?.name ??
      null,
    phone: profile?.phone ?? null,
    clientId,
    clientName: client?.name ?? null,
    clientDomain: client?.domain ?? null,
  };
}
