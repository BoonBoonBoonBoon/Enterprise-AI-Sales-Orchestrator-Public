'use client';

import { Header } from '@/components/layout';
import {
  TrendingUp,
  TrendingDown,
  Mail,
  Users,
  Calendar,
  MessageSquare,
  ArrowUpRight,
  Clock,
} from 'lucide-react';
import { cn } from '@/lib/utils';

const metrics = [
  {
    name: 'Emails Sent',
    value: '1,247',
    change: '+12.5%',
    trend: 'up',
    icon: Mail,
    color: 'blue',
    period: 'Last 30 days',
  },
  {
    name: 'Reply Rate',
    value: '24.3%',
    change: '+3.2%',
    trend: 'up',
    icon: MessageSquare,
    color: 'emerald',
    period: 'Last 30 days',
  },
  {
    name: 'Meetings Booked',
    value: '32',
    change: '+8',
    trend: 'up',
    icon: Calendar,
    color: 'purple',
    period: 'Last 30 days',
  },
  {
    name: 'Leads Generated',
    value: '156',
    change: '-2.1%',
    trend: 'down',
    icon: Users,
    color: 'amber',
    period: 'Last 30 days',
  },
];

const weeklyData = [
  { day: 'Mon', sent: 42, replies: 12 },
  { day: 'Tue', sent: 38, replies: 9 },
  { day: 'Wed', sent: 55, replies: 15 },
  { day: 'Thu', sent: 47, replies: 11 },
  { day: 'Fri', sent: 62, replies: 18 },
  { day: 'Sat', sent: 12, replies: 4 },
  { day: 'Sun', sent: 8, replies: 2 },
];

const topPerformingSubjects = [
  { subject: 'Quick question about [Company]', openRate: 68, replyRate: 28 },
  { subject: 'Noticed you mentioned [Topic]...', openRate: 64, replyRate: 25 },
  { subject: 'Re: Following up', openRate: 72, replyRate: 22 },
  { subject: 'Partnership opportunity', openRate: 58, replyRate: 18 },
  { subject: 'Can I get 10 minutes?', openRate: 52, replyRate: 15 },
];

const recentCampaigns = [
  { name: 'Q1 Outreach', sent: 450, opened: 312, replied: 78, meetings: 12, status: 'active' },
  { name: 'Enterprise Push', sent: 280, opened: 196, replied: 42, meetings: 8, status: 'active' },
  { name: 'Re-engagement', sent: 320, opened: 198, replied: 35, meetings: 5, status: 'paused' },
  { name: 'Event Follow-up', sent: 197, opened: 142, replied: 28, meetings: 7, status: 'completed' },
];

const colorMap: Record<string, string> = {
  blue: 'bg-blue-500/10 text-blue-600',
  emerald: 'bg-emerald-500/10 text-emerald-600',
  purple: 'bg-purple-500/10 text-purple-600',
  amber: 'bg-amber-500/10 text-amber-600',
};

const statusColors: Record<string, string> = {
  active: 'bg-emerald-100 text-emerald-700',
  paused: 'bg-amber-100 text-amber-700',
  completed: 'bg-gray-100 text-gray-700',
};

export default function AnalyticsPage() {
  const maxSent = Math.max(...weeklyData.map((d) => d.sent));

  return (
    <div className="flex flex-col h-full">
      <Header title="Analytics" description="Track your outreach performance" />

      <div className="flex-1 p-6 space-y-6 overflow-auto">
        {/* Metrics */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {metrics.map((metric) => (
            <div
              key={metric.name}
              className="p-5 rounded-xl border border-border bg-card hover:shadow-sm transition-shadow"
            >
              <div className="flex items-center justify-between mb-4">
                <div className={cn('p-2 rounded-lg', colorMap[metric.color])}>
                  <metric.icon className="h-4 w-4" />
                </div>
                <div
                  className={cn(
                    'flex items-center gap-1 text-xs font-medium',
                    metric.trend === 'up' ? 'text-emerald-600' : 'text-red-600'
                  )}
                >
                  {metric.trend === 'up' ? (
                    <TrendingUp className="h-3 w-3" />
                  ) : (
                    <TrendingDown className="h-3 w-3" />
                  )}
                  {metric.change}
                </div>
              </div>
              <div className="text-2xl font-bold mb-1">{metric.value}</div>
              <div className="text-sm text-muted-foreground">{metric.name}</div>
              <div className="text-xs text-muted-foreground mt-1">{metric.period}</div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Weekly Activity */}
          <div className="rounded-xl border border-border bg-card p-5">
            <div className="flex items-center justify-between mb-6">
              <h2 className="font-semibold">Weekly Activity</h2>
              <div className="flex items-center gap-4 text-xs">
                <div className="flex items-center gap-1.5">
                  <div className="w-2.5 h-2.5 rounded-full bg-primary" />
                  <span className="text-muted-foreground">Emails Sent</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <div className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
                  <span className="text-muted-foreground">Replies</span>
                </div>
              </div>
            </div>

            <div className="flex items-end justify-between h-40 gap-4">
              {weeklyData.map((day) => (
                <div key={day.day} className="flex-1 flex flex-col items-center gap-1">
                  <div className="w-full flex gap-1 items-end h-32">
                    <div
                      className="flex-1 bg-primary/20 rounded-t"
                      style={{ height: `${(day.sent / maxSent) * 100}%` }}
                    />
                    <div
                      className="flex-1 bg-emerald-500/40 rounded-t"
                      style={{ height: `${(day.replies / maxSent) * 100}%` }}
                    />
                  </div>
                  <span className="text-xs text-muted-foreground">{day.day}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Top Subject Lines */}
          <div className="rounded-xl border border-border bg-card p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold">Top Subject Lines</h2>
              <button className="text-sm text-primary hover:underline flex items-center gap-1">
                View all <ArrowUpRight className="h-3 w-3" />
              </button>
            </div>

            <div className="space-y-3">
              {topPerformingSubjects.map((item, i) => (
                <div key={i} className="flex items-center gap-4">
                  <span className="text-sm text-muted-foreground w-4">{i + 1}</span>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium truncate">{item.subject}</div>
                    <div className="flex items-center gap-3 text-xs text-muted-foreground mt-0.5">
                      <span>{item.openRate}% open</span>
                      <span>{item.replyRate}% reply</span>
                    </div>
                  </div>
                  <div
                    className={cn(
                      'w-16 h-2 rounded-full bg-gray-100 overflow-hidden'
                    )}
                  >
                    <div
                      className="h-full bg-primary rounded-full"
                      style={{ width: `${item.replyRate}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Recent Campaigns */}
        <div className="rounded-xl border border-border bg-card">
          <div className="p-5 border-b border-border flex items-center justify-between">
            <h2 className="font-semibold">Campaigns</h2>
            <button className="text-sm text-primary hover:underline flex items-center gap-1">
              Manage campaigns <ArrowUpRight className="h-3 w-3" />
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-secondary/50">
                <tr>
                  <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-5 py-3">
                    Campaign
                  </th>
                  <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-5 py-3">
                    Status
                  </th>
                  <th className="text-right text-xs font-medium text-muted-foreground uppercase tracking-wider px-5 py-3">
                    Sent
                  </th>
                  <th className="text-right text-xs font-medium text-muted-foreground uppercase tracking-wider px-5 py-3">
                    Open Rate
                  </th>
                  <th className="text-right text-xs font-medium text-muted-foreground uppercase tracking-wider px-5 py-3">
                    Reply Rate
                  </th>
                  <th className="text-right text-xs font-medium text-muted-foreground uppercase tracking-wider px-5 py-3">
                    Meetings
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {recentCampaigns.map((campaign) => {
                  const openRate = Math.round((campaign.opened / campaign.sent) * 100);
                  const replyRate = Math.round((campaign.replied / campaign.sent) * 100);

                  return (
                    <tr key={campaign.name} className="hover:bg-secondary/30 transition-colors">
                      <td className="px-5 py-4">
                        <span className="font-medium text-sm">{campaign.name}</span>
                      </td>
                      <td className="px-5 py-4">
                        <span
                          className={cn(
                            'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium capitalize',
                            statusColors[campaign.status]
                          )}
                        >
                          {campaign.status}
                        </span>
                      </td>
                      <td className="px-5 py-4 text-right text-sm">{campaign.sent}</td>
                      <td className="px-5 py-4 text-right text-sm">{openRate}%</td>
                      <td className="px-5 py-4 text-right text-sm">{replyRate}%</td>
                      <td className="px-5 py-4 text-right text-sm">{campaign.meetings}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Response Time */}
        <div className="rounded-xl border border-border bg-card p-5">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 rounded-lg bg-primary/10 text-primary">
              <Clock className="h-4 w-4" />
            </div>
            <div>
              <h3 className="font-semibold">Average Response Time</h3>
              <p className="text-sm text-muted-foreground">How fast Monty responds to incoming emails</p>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-6">
            <div className="text-center p-4 rounded-lg bg-secondary/50">
              <div className="text-3xl font-bold text-primary">2.3</div>
              <div className="text-sm text-muted-foreground">Minutes (Avg)</div>
            </div>
            <div className="text-center p-4 rounded-lg bg-secondary/50">
              <div className="text-3xl font-bold text-emerald-600">98%</div>
              <div className="text-sm text-muted-foreground">Under 5 mins</div>
            </div>
            <div className="text-center p-4 rounded-lg bg-secondary/50">
              <div className="text-3xl font-bold text-purple-600">24/7</div>
              <div className="text-sm text-muted-foreground">Coverage</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
