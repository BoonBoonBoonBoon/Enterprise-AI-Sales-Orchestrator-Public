import { createClient } from './supabase/client';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function fetchWithAuth(
  endpoint: string,
  init: RequestInit = {}
): Promise<Response> {
  const supabase = createClient();
  const { data: { session } } = await supabase.auth.getSession();

  const headers = new Headers(init.headers || {});
  headers.set('Content-Type', 'application/json');

  if (session?.access_token) {
    headers.set('Authorization', `Bearer ${session.access_token}`);
  }

  const url = endpoint.startsWith('http') ? endpoint : `${API_URL}${endpoint}`;

  return fetch(url, {
    ...init,
    headers,
  });
}

export async function apiGet<T>(endpoint: string): Promise<T> {
  const res = await fetchWithAuth(endpoint);
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function apiPost<T>(endpoint: string, data?: unknown): Promise<T> {
  const res = await fetchWithAuth(endpoint, {
    method: 'POST',
    body: data ? JSON.stringify(data) : undefined,
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function apiDelete<T>(endpoint: string): Promise<T> {
  const res = await fetchWithAuth(endpoint, {
    method: 'DELETE',
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

// ─────────────────────────────────────────────────────────────────────────────
// Type Definitions
// ─────────────────────────────────────────────────────────────────────────────

export interface Draft {
  id: string;
  from_email: string;
  from_name: string;
  subject: string;
  mailbox: string;
  status: 'pending' | 'approved' | 'rejected' | 'sent' | 'failed';
  received_at: string;
  lead?: {
    name: string;
    company?: string;
    role?: string;
    email: string;
  };
  context: Array<{ from_: string; content: string; date: string }>;
  draft_content: string;
  correlation_id: string;
}

export interface DraftListResponse {
  drafts: Draft[];
  total: number;
  page: number;
  page_size: number;
}

export interface DashboardStats {
  pending_drafts: number;
  drafts_approved_today: number;
  drafts_rejected_today: number;
  total_leads: number;
  new_leads_today: number;
  active_conversations: number;
  emails_sent_today: number;
  emails_received_today: number;
  response_rate: number;
  connected_mailboxes: number;
  mailbox_errors: number;
}

export interface LeadStatusBreakdown {
  new: number;
  contacted: number;
  qualified: number;
  converted: number;
  lost: number;
}

export interface StatsResponse {
  dashboard: DashboardStats;
  lead_breakdown: LeadStatusBreakdown;
  period_start: string;
  period_end: string;
}

export interface QuickStats {
  pending_drafts: number;
  total_leads: number;
  connected_mailboxes: number;
}

export interface Mailbox {
  id: string;
  email: string;
  provider: 'gmail' | 'outlook' | 'imap';
  status: 'connected' | 'disconnected' | 'error';
  last_sync?: string;
  messages_received: number;
  messages_sent: number;
  error?: string;
}

export interface MailboxListResponse {
  mailboxes: Mailbox[];
  total: number;
}

// ─────────────────────────────────────────────────────────────────────────────
// API Functions
// ─────────────────────────────────────────────────────────────────────────────

// Stats
export const getStats = () => apiGet<StatsResponse>('/api/v1/stats');
export const getQuickStats = () => apiGet<QuickStats>('/api/v1/stats/quick');

// Drafts
export const getDrafts = (params?: { status?: string; page?: number; page_size?: number }) => {
  const query = new URLSearchParams();
  if (params?.status) query.set('status', params.status);
  if (params?.page) query.set('page', String(params.page));
  if (params?.page_size) query.set('page_size', String(params.page_size));
  const qs = query.toString();
  return apiGet<DraftListResponse>(`/api/v1/drafts${qs ? `?${qs}` : ''}`);
};

export const getDraft = (id: string) => apiGet<Draft>(`/api/v1/drafts/${id}`);

export const approveDraft = (id: string, content?: string) =>
  apiPost<{ message: string; draft_id: string; status: string }>(`/api/v1/drafts/${id}/approve`, content ? { content } : undefined);

export const rejectDraft = (id: string, reason: string) =>
  apiPost<{ message: string; draft_id: string; status: string }>(`/api/v1/drafts/${id}/reject`, { reason });

export const rewriteDraft = (id: string) =>
  apiPost<{ message: string; draft_id: string }>(`/api/v1/drafts/${id}/rewrite`);

// Mailboxes
export const getMailboxes = () => apiGet<MailboxListResponse>('/api/v1/mailboxes');
export const getMailbox = (id: string) => apiGet<Mailbox>(`/api/v1/mailboxes/${id}`);
export const disconnectMailbox = (id: string) => apiDelete<{ message: string }>(`/api/v1/mailboxes/${id}`);
export const syncMailbox = (id: string) => apiPost<{ message: string }>(`/api/v1/mailboxes/${id}/sync`);
