'use client';

import useSWR from 'swr';
import {
  getStats,
  getQuickStats,
  getDrafts,
  getDraft,
  getMailboxes,
  type StatsResponse,
  type QuickStats,
  type DraftListResponse,
  type Draft,
  type MailboxListResponse,
} from './api';

// ─────────────────────────────────────────────────────────────────────────────
// Stats Hooks
// ─────────────────────────────────────────────────────────────────────────────

export function useStats() {
  const { data, error, isLoading, mutate } = useSWR<StatsResponse>(
    '/api/v1/stats',
    () => getStats(),
    {
      refreshInterval: 30000, // Refresh every 30 seconds
      revalidateOnFocus: true,
    }
  );

  return {
    stats: data,
    isLoading,
    isError: error,
    refresh: mutate,
  };
}

export function useQuickStats() {
  const { data, error, isLoading, mutate } = useSWR<QuickStats>(
    '/api/v1/stats/quick',
    () => getQuickStats(),
    {
      refreshInterval: 10000, // Refresh every 10 seconds for header
      revalidateOnFocus: true,
    }
  );

  return {
    stats: data,
    isLoading,
    isError: error,
    refresh: mutate,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Drafts Hooks
// ─────────────────────────────────────────────────────────────────────────────

export function useDrafts(params?: { status?: string; page?: number; page_size?: number }): {
  drafts: Draft[];
  total: number;
  page: number;
  pageSize: number;
  isLoading: boolean;
  isError: unknown;
  refresh: () => void;
} {
  const key = `/api/v1/drafts?${JSON.stringify(params || {})}`;
  
  const { data, error, isLoading, mutate } = useSWR<DraftListResponse>(
    key,
    () => getDrafts(params),
    {
      refreshInterval: 15000, // Refresh every 15 seconds
      revalidateOnFocus: true,
    }
  );

  return {
    drafts: data?.drafts ?? [],
    total: data?.total ?? 0,
    page: data?.page ?? 1,
    pageSize: data?.page_size ?? 20,
    isLoading,
    isError: error,
    refresh: mutate,
  };
}

export function usePendingDrafts() {
  return useDrafts({ status: 'pending' });
}

export function useDraft(id: string | null) {
  const { data, error, isLoading, mutate } = useSWR<Draft>(
    id ? `/api/v1/drafts/${id}` : null,
    () => (id ? getDraft(id) : Promise.reject('No ID')),
    {
      revalidateOnFocus: true,
    }
  );

  return {
    draft: data,
    isLoading,
    isError: error,
    refresh: mutate,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Mailboxes Hooks
// ─────────────────────────────────────────────────────────────────────────────

export function useMailboxes() {
  const { data, error, isLoading, mutate } = useSWR<MailboxListResponse>(
    '/api/v1/mailboxes',
    () => getMailboxes(),
    {
      refreshInterval: 60000, // Refresh every minute
      revalidateOnFocus: true,
    }
  );

  return {
    mailboxes: data?.mailboxes ?? [],
    total: data?.total ?? 0,
    isLoading,
    isError: error,
    refresh: mutate,
  };
}
