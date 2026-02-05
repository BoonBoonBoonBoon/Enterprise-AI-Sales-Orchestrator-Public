import { supabase } from './supabase';

const DEV_BYPASS_TOKEN_KEY = 'agentic:dev_bypass_token';

export function getDevBypassToken(): string | null {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem(DEV_BYPASS_TOKEN_KEY);
}

export function setDevBypassToken(token: string) {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(DEV_BYPASS_TOKEN_KEY, token);
}

export function clearDevBypassToken() {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(DEV_BYPASS_TOKEN_KEY);
}

export async function fetchWithAuth(input: RequestInfo | URL, init: RequestInit = {}) {
  const devToken = getDevBypassToken();
  const { data } = await supabase.auth.getSession();
  const accessToken = devToken || data.session?.access_token;

  const headers = new Headers(init.headers || {});
  if (accessToken) {
    headers.set('Authorization', `Bearer ${accessToken}`);
  }

  return fetch(input, {
    ...init,
    headers,
  });
}
