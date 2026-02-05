'use client';

import { useEffect, useState } from 'react';
import { Header } from '@/components/layout/header';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Search,
  Filter,
  MoreHorizontal,
  Building2,
  Mail,
  Phone,
  ExternalLink,
  CheckCircle,
  Clock,
  XCircle,
  Star,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { fetchWithAuth } from '@/lib/api';

type Lead = {
  id: string;
  name: string;
  email: string;
  company?: string;
  role?: string;
  status: 'new' | 'nurturing' | 'qualified' | 'disqualified';
  score: number;
  source: 'inbound' | 'outbound' | 'referral';
  last_contact?: string | null;
  conversations: number;
  created_at: string;
};

type LeadListResponse = {
  leads: Lead[];
  total: number;
  page: number;
  page_size: number;
};

type LeadStats = {
  total: number;
  new: number;
  nurturing: number;
  qualified: number;
  disqualified: number;
};

const statusConfig = {
  new: { label: 'New', color: 'bg-blue-500/10 text-blue-500', icon: Clock },
  nurturing: { label: 'Nurturing', color: 'bg-yellow-500/10 text-yellow-500', icon: Clock },
  qualified: { label: 'Qualified', color: 'bg-green-500/10 text-green-500', icon: CheckCircle },
  disqualified: { label: 'Disqualified', color: 'bg-red-500/10 text-red-500', icon: XCircle },
};

export default function LeadsPage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [stats, setStats] = useState<LeadStats>({ total: 0, new: 0, nurturing: 0, qualified: 0, disqualified: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string | null>(null);

  const loadLeads = async () => {
    try {
      setLoading(true);
      setError(null);
      const [leadsRes, statsRes] = await Promise.all([
        fetchWithAuth('/api/v1/leads'),
        fetchWithAuth('/api/v1/leads/stats'),
      ]);

      if (!leadsRes.ok) {
        throw new Error('Failed to load leads');
      }
      const leadsData = (await leadsRes.json()) as LeadListResponse;
      setLeads(leadsData.leads ?? []);

      if (statsRes.ok) {
        const statsData = (await statsRes.json()) as LeadStats;
        setStats(statsData);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load leads');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLeads();
  }, []);

  const filteredLeads = leads.filter((lead) => {
    const matchesSearch =
      lead.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      lead.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (lead.company ?? '').toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = !statusFilter || lead.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  return (
    <div className="flex flex-col h-full">
      <Header title="Leads" description="Manage your lead database" />

      <div className="flex-1 p-6 overflow-auto">
        {/* Stats */}
        <div className="grid gap-4 md:grid-cols-4 mb-6">
          <Card
            className={cn('cursor-pointer hover:border-primary/50 transition-colors', !statusFilter && 'border-primary')}
            onClick={() => setStatusFilter(null)}
          >
            <CardContent className="p-4">
              <p className="text-sm text-muted-foreground">Total Leads</p>
              <p className="text-2xl font-bold">{stats.total}</p>
            </CardContent>
          </Card>
          <Card
            className={cn(
              'cursor-pointer hover:border-primary/50 transition-colors',
              statusFilter === 'qualified' && 'border-primary'
            )}
            onClick={() => setStatusFilter(statusFilter === 'qualified' ? null : 'qualified')}
          >
            <CardContent className="p-4">
              <p className="text-sm text-muted-foreground">Qualified</p>
              <p className="text-2xl font-bold text-green-500">{stats.qualified}</p>
            </CardContent>
          </Card>
          <Card
            className={cn(
              'cursor-pointer hover:border-primary/50 transition-colors',
              statusFilter === 'nurturing' && 'border-primary'
            )}
            onClick={() => setStatusFilter(statusFilter === 'nurturing' ? null : 'nurturing')}
          >
            <CardContent className="p-4">
              <p className="text-sm text-muted-foreground">Nurturing</p>
              <p className="text-2xl font-bold text-yellow-500">{stats.nurturing}</p>
            </CardContent>
          </Card>
          <Card
            className={cn(
              'cursor-pointer hover:border-primary/50 transition-colors',
              statusFilter === 'new' && 'border-primary'
            )}
            onClick={() => setStatusFilter(statusFilter === 'new' ? null : 'new')}
          >
            <CardContent className="p-4">
              <p className="text-sm text-muted-foreground">New</p>
              <p className="text-2xl font-bold text-blue-500">{stats.new}</p>
            </CardContent>
          </Card>
        </div>

        {/* Search and filters */}
        <div className="flex items-center gap-4 mb-6">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search leads..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 bg-muted/30"
            />
          </div>
          <Button variant="outline" className="gap-2">
            <Filter className="h-4 w-4" />
            Filters
          </Button>
        </div>

        {/* Leads table */}
        <Card>
          <div className="overflow-x-auto">
            {loading && <div className="p-4 text-sm text-muted-foreground">Loading leads…</div>}
            {error && <div className="p-4 text-sm text-destructive">{error}</div>}
            {!loading && !error && (
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border/60">
                    <th className="text-left p-4 text-sm font-medium text-muted-foreground">Lead</th>
                    <th className="text-left p-4 text-sm font-medium text-muted-foreground">Company</th>
                    <th className="text-left p-4 text-sm font-medium text-muted-foreground">Status</th>
                    <th className="text-left p-4 text-sm font-medium text-muted-foreground">Score</th>
                    <th className="text-left p-4 text-sm font-medium text-muted-foreground">Conversations</th>
                    <th className="text-left p-4 text-sm font-medium text-muted-foreground">Source</th>
                    <th className="text-right p-4 text-sm font-medium text-muted-foreground"></th>
                  </tr>
                </thead>
                <tbody>
                  {filteredLeads.map((lead) => {
                  const StatusIcon = statusConfig[lead.status as keyof typeof statusConfig].icon;
                  return (
                    <tr
                      key={lead.id}
                      className="border-b border-border/40 hover:bg-muted/30 transition-colors cursor-pointer"
                    >
                      <td className="p-4">
                        <div className="flex items-center gap-3">
                          <div className="h-10 w-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-white text-sm font-medium">
                            {lead.name
                              .split(' ')
                              .map((n) => n[0])
                              .join('')}
                          </div>
                          <div>
                            <p className="font-medium">{lead.name}</p>
                            <p className="text-sm text-muted-foreground">{lead.email}</p>
                          </div>
                        </div>
                      </td>
                      <td className="p-4">
                        <div className="flex items-center gap-2">
                          <Building2 className="h-4 w-4 text-muted-foreground" />
                          <div>
                            <p className="font-medium">{lead.company ?? 'Unknown company'}</p>
                            <p className="text-xs text-muted-foreground">{lead.role ?? 'Role unknown'}</p>
                          </div>
                        </div>
                      </td>
                      <td className="p-4">
                        <span
                          className={cn(
                            'inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium',
                            statusConfig[lead.status as keyof typeof statusConfig].color
                          )}
                        >
                          <StatusIcon className="h-3 w-3" />
                          {statusConfig[lead.status as keyof typeof statusConfig].label}
                        </span>
                      </td>
                      <td className="p-4">
                        <div className="flex items-center gap-2">
                          <div className="w-16 h-2 rounded-full bg-muted overflow-hidden">
                            <div
                              className={cn(
                                'h-full rounded-full',
                                lead.score >= 80
                                  ? 'bg-green-500'
                                  : lead.score >= 50
                                  ? 'bg-yellow-500'
                                  : 'bg-red-500'
                              )}
                              style={{ width: `${lead.score}%` }}
                            />
                          </div>
                          <span className="text-sm font-medium">{lead.score}</span>
                        </div>
                      </td>
                      <td className="p-4">
                        <span className="text-sm">{lead.conversations}</span>
                      </td>
                      <td className="p-4">
                        <span className="text-sm text-muted-foreground capitalize">{lead.source}</span>
                      </td>
                      <td className="p-4 text-right">
                        <Button variant="ghost" size="icon">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </td>
                    </tr>
                  );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
