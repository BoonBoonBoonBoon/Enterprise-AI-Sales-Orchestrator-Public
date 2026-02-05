"use client";

import { useEffect, useState } from 'react';
import { Header } from '@/components/layout/header';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Mail, FileEdit, Users, CheckCircle, TrendingUp, Clock, AlertCircle, ArrowUpRight } from 'lucide-react';
import { fetchWithAuth } from '@/lib/api';

type LeadStats = {
  total: number;
  new: number;
  nurturing: number;
  qualified: number;
  disqualified: number;
};

type Draft = {
  id: string;
  from_email: string;
  from_name: string;
  subject: string;
  received_at: string;
  status: 'pending' | 'approved' | 'rejected' | 'sent' | 'failed';
};

type DraftListResponse = {
  drafts: Draft[];
  total: number;
  page: number;
  page_size: number;
};

const defaultStats = [
  { name: 'Emails Received', value: '—', change: '', icon: Mail, color: 'blue' },
  { name: 'Drafts Pending', value: '0', change: '', icon: FileEdit, color: 'yellow' },
  { name: 'Emails Sent', value: '—', change: '', icon: CheckCircle, color: 'green' },
  { name: 'Qualified Leads', value: '0', change: '', icon: Users, color: 'purple' },
];

const recentActivity = [
  { type: 'draft', message: 'New draft for reply to sarah@acme.com', time: '2 mins ago', status: 'pending' },
  { type: 'sent', message: 'Reply sent to mike@startup.io', time: '15 mins ago', status: 'sent' },
  { type: 'qualified', message: 'Lead qualified: TechCorp Inc.', time: '1 hour ago', status: 'success' },
  { type: 'received', message: 'New email from ceo@enterprise.co', time: '2 hours ago', status: 'new' },
  { type: 'draft', message: 'Draft ready for james@bigco.com', time: '3 hours ago', status: 'pending' },
];

const colorMap = {
  blue: 'bg-blue-500/10 text-blue-500',
  yellow: 'bg-yellow-500/10 text-yellow-500',
  green: 'bg-green-500/10 text-green-500',
  purple: 'bg-purple-500/10 text-purple-500',
};

export default function DashboardPage() {
  const [stats, setStats] = useState(defaultStats);
  const [drafts, setDrafts] = useState<Draft[]>([]);

  useEffect(() => {
    const loadDashboard = async () => {
      try {
        const [draftRes, statsRes] = await Promise.all([
          fetchWithAuth('/api/v1/drafts'),
          fetchWithAuth('/api/v1/leads/stats'),
        ]);

        if (draftRes.ok) {
          const data = (await draftRes.json()) as DraftListResponse;
          const pendingCount = (data.drafts ?? []).filter((d) => d.status === 'pending').length;
          setDrafts(data.drafts ?? []);
          setStats((prev) =>
            prev.map((stat) =>
              stat.name === 'Drafts Pending' ? { ...stat, value: String(pendingCount) } : stat
            )
          );
        }

        if (statsRes.ok) {
          const statsData = (await statsRes.json()) as LeadStats;
          setStats((prev) =>
            prev.map((stat) =>
              stat.name === 'Qualified Leads' ? { ...stat, value: String(statsData.qualified) } : stat
            )
          );
        }
      } catch {
        setDrafts([]);
      }
    };

    loadDashboard();
  }, []);

  const pendingDrafts = drafts.filter((draft) => draft.status === 'pending').slice(0, 3);

  return (
    <div className="flex flex-col h-full">
      <Header title="Dashboard" description="Welcome back, here's your overview" />

      <div className="flex-1 p-6 space-y-6 overflow-auto">
        {/* Stats Grid */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {stats.map((stat) => (
            <Card key={stat.name} className="relative overflow-hidden">
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">{stat.name}</CardTitle>
                <div className={`p-2 rounded-lg ${colorMap[stat.color as keyof typeof colorMap]}`}>
                  <stat.icon className="h-4 w-4" />
                </div>
              </CardHeader>
              <CardContent>
                <div className="flex items-baseline gap-2">
                  <span className="text-3xl font-bold">{stat.value}</span>
                  {stat.change && (
                    <span className="flex items-center text-sm text-green-500">
                      <TrendingUp className="h-3 w-3 mr-0.5" />
                      {stat.change}
                    </span>
                  )}
                </div>
              </CardContent>
              {/* Decorative gradient */}
              <div className="absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r from-transparent via-primary/20 to-transparent" />
            </Card>
          ))}
        </div>

        {/* Main content grid */}
        <div className="grid gap-6 lg:grid-cols-3">
          {/* Pending Drafts */}
          <Card className="lg:col-span-2">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-lg">Pending Drafts</CardTitle>
              <a href="/dashboard/drafts" className="text-sm text-primary flex items-center hover:underline">
                View all <ArrowUpRight className="h-3 w-3 ml-1" />
              </a>
            </CardHeader>
            <CardContent className="space-y-4">
              {pendingDrafts.length === 0 && (
                <div className="text-sm text-muted-foreground">No pending drafts.</div>
              )}
              {pendingDrafts.map((draft) => (
                <div
                  key={draft.id}
                  className="flex items-start gap-4 p-4 rounded-lg border border-border/60 bg-muted/20 hover:bg-muted/40 transition-colors cursor-pointer"
                >
                  <div className="h-10 w-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-white text-sm font-medium flex-shrink-0">
                    {draft.from_name
                      .split(' ')
                      .map((n) => n[0])
                      .join('')}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="font-medium truncate">{draft.from_email}</p>
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-yellow-500/10 text-yellow-500">
                        <Clock className="h-3 w-3 mr-1" />
                        Pending
                      </span>
                    </div>
                    <p className="text-sm text-muted-foreground truncate mt-0.5">
                      {draft.subject}
                    </p>
                  </div>
                  <span className="text-xs text-muted-foreground whitespace-nowrap">
                    {new Date(draft.received_at).toLocaleTimeString()}
                  </span>
                </div>
              ))}
            </CardContent>
          </Card>

          {/* Recent Activity */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Recent Activity</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {recentActivity.map((activity, i) => (
                  <div key={i} className="flex items-start gap-3">
                    <div className="mt-0.5">
                      {activity.status === 'pending' && (
                        <div className="h-2 w-2 rounded-full bg-yellow-500" />
                      )}
                      {activity.status === 'sent' && (
                        <div className="h-2 w-2 rounded-full bg-green-500" />
                      )}
                      {activity.status === 'success' && (
                        <div className="h-2 w-2 rounded-full bg-purple-500" />
                      )}
                      {activity.status === 'new' && (
                        <div className="h-2 w-2 rounded-full bg-blue-500" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm truncate">{activity.message}</p>
                      <p className="text-xs text-muted-foreground">{activity.time}</p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Quick Actions */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Quick Actions</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <button className="flex items-center gap-3 p-4 rounded-lg border border-border/60 hover:border-primary/50 hover:bg-muted/30 transition-all text-left group">
              <div className="p-2 rounded-lg bg-blue-500/10 text-blue-500 group-hover:bg-blue-500/20 transition-colors">
                <Mail className="h-5 w-5" />
              </div>
              <div>
                <p className="font-medium">Connect Mailbox</p>
                <p className="text-xs text-muted-foreground">Add a new inbox</p>
              </div>
            </button>

            <button className="flex items-center gap-3 p-4 rounded-lg border border-border/60 hover:border-primary/50 hover:bg-muted/30 transition-all text-left group">
              <div className="p-2 rounded-lg bg-green-500/10 text-green-500 group-hover:bg-green-500/20 transition-colors">
                <CheckCircle className="h-5 w-5" />
              </div>
              <div>
                <p className="font-medium">Review Drafts</p>
                <p className="text-xs text-muted-foreground">{pendingDrafts.length} pending approval</p>
              </div>
            </button>

            <button className="flex items-center gap-3 p-4 rounded-lg border border-border/60 hover:border-primary/50 hover:bg-muted/30 transition-all text-left group">
              <div className="p-2 rounded-lg bg-purple-500/10 text-purple-500 group-hover:bg-purple-500/20 transition-colors">
                <Users className="h-5 w-5" />
              </div>
              <div>
                <p className="font-medium">View Leads</p>
                <p className="text-xs text-muted-foreground">156 qualified leads</p>
              </div>
            </button>

            <button className="flex items-center gap-3 p-4 rounded-lg border border-border/60 hover:border-primary/50 hover:bg-muted/30 transition-all text-left group">
              <div className="p-2 rounded-lg bg-orange-500/10 text-orange-500 group-hover:bg-orange-500/20 transition-colors">
                <AlertCircle className="h-5 w-5" />
              </div>
              <div>
                <p className="font-medium">View Failures</p>
                <p className="text-xs text-muted-foreground">2 need attention</p>
              </div>
            </button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
