'use client';

import { Header } from '@/components/layout';
import { useStats, usePendingDrafts } from '@/lib/hooks';
import { approveDraft, rejectDraft } from '@/lib/api';
import {
  Mail,
  FileEdit,
  Users,
  TrendingUp,
  Clock,
  CheckCircle,
  ArrowUpRight,
  AlertCircle,
  Loader2,
} from 'lucide-react';
import { useState } from 'react';

const recentActivity = [
  { type: 'draft', message: 'New draft for reply to sarah@acme.com', time: '2 mins ago', status: 'pending' },
  { type: 'sent', message: 'Reply sent to mike@startup.io', time: '15 mins ago', status: 'sent' },
  { type: 'qualified', message: 'Lead qualified: TechCorp Inc.', time: '1 hour ago', status: 'success' },
  { type: 'received', message: 'New email from ceo@enterprise.co', time: '2 hours ago', status: 'new' },
  { type: 'meeting', message: 'Meeting booked with julia@growth.co', time: '3 hours ago', status: 'success' },
];

const colorMap: Record<string, string> = {
  amber: 'bg-amber-500/10 text-amber-600',
  blue: 'bg-blue-500/10 text-blue-600',
  emerald: 'bg-emerald-500/10 text-emerald-600',
  purple: 'bg-purple-500/10 text-purple-600',
};

const statusMap: Record<string, { color: string; icon: typeof CheckCircle }> = {
  pending: { color: 'text-amber-500', icon: Clock },
  sent: { color: 'text-blue-500', icon: Mail },
  success: { color: 'text-emerald-500', icon: CheckCircle },
  new: { color: 'text-purple-500', icon: AlertCircle },
};

export default function DashboardPage() {
  const { stats, isLoading: statsLoading } = useStats();
  const { drafts, isLoading: draftsLoading, refresh: refreshDrafts } = usePendingDrafts();
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const handleApprove = async (draftId: string) => {
    setActionLoading(draftId);
    try {
      await approveDraft(draftId);
      await refreshDrafts();
    } catch (err) {
      console.error('Failed to approve draft:', err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleReject = async (draftId: string) => {
    setActionLoading(draftId);
    try {
      await rejectDraft(draftId, 'Rejected from dashboard');
      await refreshDrafts();
    } catch (err) {
      console.error('Failed to reject draft:', err);
    } finally {
      setActionLoading(null);
    }
  };

  // Build stats array from API data
  const dashboard = stats?.dashboard;
  const statCards = [
    { 
      name: 'Drafts Pending', 
      value: statsLoading ? '...' : String(dashboard?.pending_drafts ?? 0), 
      change: `${dashboard?.drafts_approved_today ?? 0} approved today`, 
      icon: FileEdit, 
      color: 'amber' 
    },
    { 
      name: 'Emails Sent', 
      value: statsLoading ? '...' : String(dashboard?.emails_sent_today ?? 0), 
      change: 'Today', 
      icon: Mail, 
      color: 'blue' 
    },
    { 
      name: 'Active Leads', 
      value: statsLoading ? '...' : String(dashboard?.total_leads ?? 0), 
      change: `${dashboard?.new_leads_today ?? 0} new`, 
      icon: Users, 
      color: 'emerald' 
    },
    { 
      name: 'Response Rate', 
      value: statsLoading ? '...' : `${Math.round((dashboard?.response_rate ?? 0) * 100)}%`, 
      change: 'This month', 
      icon: TrendingUp, 
      color: 'purple' 
    },
  ];

  return (
    <div className="flex flex-col h-full">
      <Header title="Dashboard" description="Welcome back! Here's what's happening." />

      <div className="flex-1 p-6 space-y-6 overflow-auto">
        {/* Monty status */}
        <div className="rounded-xl border border-border bg-card p-5">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Monty status</p>
              <div className="mt-2 flex items-center gap-2">
                <span className="inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500 animate-pulse" />
                <span className="font-semibold">Active</span>
                <span className="text-xs text-muted-foreground">
                  Monitoring {statsLoading ? '...' : dashboard?.connected_mailboxes ?? 0} inbox{dashboard?.connected_mailboxes !== 1 ? 'es' : ''}
                </span>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
              <div className="flex items-center gap-2 rounded-lg border border-border px-3 py-1.5">
                <FileEdit className="h-4 w-4 text-amber-500" />
                <span>{statsLoading ? '...' : dashboard?.pending_drafts ?? 0} drafts ready</span>
              </div>
              <div className="flex items-center gap-2 rounded-lg border border-border px-3 py-1.5">
                <Clock className="h-4 w-4 text-blue-500" />
                <span>Next check in 5 min</span>
              </div>
            </div>
          </div>
        </div>

        {/* Onboarding progress */}
        <div className="rounded-xl border border-border bg-card p-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="font-semibold">Get started with Monty</h2>
              <p className="text-sm text-muted-foreground mt-1">2 of 4 complete</p>
            </div>
            <span className="text-xs text-muted-foreground rounded-full border border-border px-3 py-1.5">
              Setup checklist
            </span>
          </div>

          <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="flex items-center gap-3 rounded-lg border border-border px-3 py-2">
              <CheckCircle className="h-4 w-4 text-emerald-500" />
              <div className="min-w-0">
                <p className="text-sm font-medium">Connect your inbox</p>
                <p className="text-xs text-muted-foreground">Gmail or Outlook</p>
              </div>
            </div>
            <div className="flex items-center gap-3 rounded-lg border border-border px-3 py-2">
              <CheckCircle className="h-4 w-4 text-emerald-500" />
              <div className="min-w-0">
                <p className="text-sm font-medium">Set your voice</p>
                <p className="text-xs text-muted-foreground">Tone + examples</p>
              </div>
            </div>
            <div className="flex items-center gap-3 rounded-lg border border-border px-3 py-2">
              <Clock className="h-4 w-4 text-amber-500" />
              <div className="min-w-0">
                <p className="text-sm font-medium">Approve your first draft</p>
                <p className="text-xs text-muted-foreground">Review queue</p>
              </div>
            </div>
            <div className="flex items-center gap-3 rounded-lg border border-border px-3 py-2">
              <Clock className="h-4 w-4 text-amber-500" />
              <div className="min-w-0">
                <p className="text-sm font-medium">Enable autopilot rules</p>
                <p className="text-xs text-muted-foreground">Guardrails + schedules</p>
              </div>
            </div>
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {statCards.map((stat) => (
            <div
              key={stat.name}
              className="p-5 rounded-xl border border-border bg-card hover:shadow-sm transition-shadow"
            >
              <div className="flex items-center justify-between mb-3">
                <div className={`p-2 rounded-lg ${colorMap[stat.color]}`}>
                  <stat.icon className="h-4 w-4" />
                </div>
                <span className="text-xs text-muted-foreground">{stat.change}</span>
              </div>
              <div className="text-2xl font-bold">{stat.value}</div>
              <div className="text-sm text-muted-foreground">{stat.name}</div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Pending Drafts */}
          <div className="lg:col-span-2 rounded-xl border border-border bg-card">
            <div className="p-4 border-b border-border flex items-center justify-between">
              <h2 className="font-semibold">Pending Drafts</h2>
              <a href="/dashboard/inbox" className="text-sm text-primary hover:underline flex items-center gap-1">
                View all <ArrowUpRight className="h-3 w-3" />
              </a>
            </div>
            {draftsLoading ? (
              <div className="p-8 flex items-center justify-center">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : drafts.length === 0 ? (
              <div className="p-8 text-center text-muted-foreground">
                <FileEdit className="h-8 w-8 mx-auto mb-2 opacity-50" />
                <p>No pending drafts</p>
                <p className="text-xs mt-1">Monty will create drafts when new emails arrive</p>
              </div>
            ) : (
              <div className="divide-y divide-border">
                {drafts.slice(0, 3).map((draft) => (
                  <div
                    key={draft.id}
                    className="p-4 hover:bg-secondary/50 transition-colors cursor-pointer"
                  >
                    <div className="flex items-start justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{draft.lead?.name || draft.from_name}</span>
                        <span className="text-xs text-muted-foreground">{draft.from_email}</span>
                      </div>
                      <span className="text-xs text-muted-foreground">
                        {new Date(draft.received_at).toLocaleDateString()}
                      </span>
                    </div>
                    <div className="text-sm font-medium mb-1">{draft.subject}</div>
                    <div className="text-sm text-muted-foreground line-clamp-1">{draft.draft_content}</div>
                    <div className="mt-3 flex items-center gap-2">
                      <button 
                        onClick={() => handleApprove(draft.id)}
                        disabled={actionLoading === draft.id}
                        className="px-3 py-1.5 text-xs font-medium rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50 flex items-center gap-1"
                      >
                        {actionLoading === draft.id && <Loader2 className="h-3 w-3 animate-spin" />}
                        Approve & Send
                      </button>
                      <button 
                        onClick={() => handleReject(draft.id)}
                        disabled={actionLoading === draft.id}
                        className="px-3 py-1.5 text-xs font-medium rounded-lg border border-input hover:bg-secondary transition-colors disabled:opacity-50"
                      >
                        Reject
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Recent Activity */}
          <div className="rounded-xl border border-border bg-card">
            <div className="p-4 border-b border-border">
              <h2 className="font-semibold">Recent Activity</h2>
            </div>
            <div className="p-4 space-y-4">
              {recentActivity.map((activity, i) => {
                const StatusIcon = statusMap[activity.status]?.icon || Clock;
                const statusColor = statusMap[activity.status]?.color || 'text-muted-foreground';

                return (
                  <div key={i} className="flex items-start gap-3">
                    <div className={`mt-0.5 ${statusColor}`}>
                      <StatusIcon className="h-4 w-4" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm line-clamp-2">{activity.message}</p>
                      <p className="text-xs text-muted-foreground mt-0.5">{activity.time}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
