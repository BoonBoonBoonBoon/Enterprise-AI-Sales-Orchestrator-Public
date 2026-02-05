'use client';

import { useState } from 'react';
import { Header } from '@/components/layout';
import {
  Mail,
  Clock,
  CheckCircle,
  XCircle,
  Edit3,
  Send,
  ChevronDown,
  Filter,
  Search,
} from 'lucide-react';
import { cn } from '@/lib/utils';

type DraftStatus = 'pending' | 'approved' | 'rejected' | 'sent';

interface Draft {
  id: string;
  to: string;
  toEmail: string;
  subject: string;
  body: string;
  createdAt: string;
  status: DraftStatus;
  context: string;
}

const mockDrafts: Draft[] = [
  {
    id: '1',
    to: 'Sarah Chen',
    toEmail: 'sarah@acme.com',
    subject: 'Re: Pricing question for enterprise',
    body: `Hi Sarah,

Thanks for reaching out about our enterprise pricing! I'd be happy to walk you through our options.

For teams of 20+, we offer custom pricing with volume discounts, priority support, and dedicated onboarding. Based on what you mentioned about your team size, I think our Team plan at $39/seat/month (billed annually) would be a great fit.

Would you have time for a quick 15-minute call this week? I can show you exactly how other companies like yours are using Monty.

Best,
[Your name]`,
    createdAt: '2 mins ago',
    status: 'pending',
    context: 'Sarah asked about enterprise pricing for a 25-person sales team',
  },
  {
    id: '2',
    to: 'Marcus Johnson',
    toEmail: 'marcus@startup.io',
    subject: 'Following up on our demo',
    body: `Hi Marcus,

I wanted to follow up on the demo we had last Thursday. You mentioned wanting to see how Monty handles multi-inbox workflows—I've attached a quick video walkthrough that shows exactly that.

Any questions as you're evaluating? Happy to hop on a call anytime.

Best,
[Your name]`,
    createdAt: '15 mins ago',
    status: 'pending',
    context: 'Marcus had a demo last week and was interested in multi-inbox support',
  },
  {
    id: '3',
    to: 'Elena Rodriguez',
    toEmail: 'elena@bigcorp.com',
    subject: 'Re: Partnership inquiry',
    body: `Hi Elena,

Thank you for your interest in partnering with us! We're definitely open to exploring this.

I'd love to learn more about what you have in mind. Could you share a bit more about the integration you're envisioning?

Looking forward to hearing from you.

Best,
[Your name]`,
    createdAt: '1 hour ago',
    status: 'pending',
    context: 'Elena reached out about a potential API integration partnership',
  },
  {
    id: '4',
    to: 'James Wilson',
    toEmail: 'james@techstartup.com',
    subject: 'Re: Quick question about automation',
    body: `Hi James,

Great question! Yes, Monty can run in full autopilot mode once you're comfortable. Most customers start in review mode for a week or two, then gradually enable automation.

You can set guardrails like sending limits, allowed domains, and confidence thresholds to ensure it only sends when you'd approve anyway.

Want me to set up a trial so you can see it in action?

Best,
[Your name]`,
    createdAt: '2 hours ago',
    status: 'approved',
    context: 'James asked about automation capabilities and guardrails',
  },
];

const statusConfig: Record<DraftStatus, { label: string; color: string; icon: typeof Clock }> = {
  pending: { label: 'Pending Review', color: 'bg-amber-500/10 text-amber-600 border-amber-200', icon: Clock },
  approved: { label: 'Approved', color: 'bg-emerald-500/10 text-emerald-600 border-emerald-200', icon: CheckCircle },
  rejected: { label: 'Rejected', color: 'bg-red-500/10 text-red-600 border-red-200', icon: XCircle },
  sent: { label: 'Sent', color: 'bg-blue-500/10 text-blue-600 border-blue-200', icon: Send },
};

export default function InboxPage() {
  const [drafts, setDrafts] = useState(mockDrafts);
  const [selectedDraft, setSelectedDraft] = useState<Draft | null>(mockDrafts[0]);
  const [filter, setFilter] = useState<DraftStatus | 'all'>('all');

  const filteredDrafts = filter === 'all' ? drafts : drafts.filter((d) => d.status === filter);
  const pendingCount = drafts.filter((d) => d.status === 'pending').length;

  const handleApprove = (id: string) => {
    setDrafts((prev) =>
      prev.map((d) => (d.id === id ? { ...d, status: 'approved' as DraftStatus } : d))
    );
  };

  const handleReject = (id: string) => {
    setDrafts((prev) =>
      prev.map((d) => (d.id === id ? { ...d, status: 'rejected' as DraftStatus } : d))
    );
  };

  return (
    <div className="flex flex-col h-full">
      <Header
        title="Inbox"
        description={`${pendingCount} draft${pendingCount !== 1 ? 's' : ''} pending review`}
      />

      <div className="flex-1 flex overflow-hidden">
        {/* Draft List */}
        <div className="w-96 border-r border-border flex flex-col">
          {/* Filters */}
          <div className="p-4 border-b border-border space-y-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search drafts..."
                className="w-full pl-9 pr-4 py-2 rounded-lg border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div className="flex items-center gap-2">
              <button className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-input hover:bg-secondary transition-colors">
                <Filter className="h-3 w-3" />
                Filter
                <ChevronDown className="h-3 w-3" />
              </button>
              <div className="flex-1" />
              <span className="text-xs text-muted-foreground">{filteredDrafts.length} drafts</span>
            </div>
          </div>

          {/* Draft List */}
          <div className="flex-1 overflow-auto">
            {filteredDrafts.map((draft) => {
              const config = statusConfig[draft.status];
              const isSelected = selectedDraft?.id === draft.id;

              return (
                <div
                  key={draft.id}
                  onClick={() => setSelectedDraft(draft)}
                  className={cn(
                    'p-4 border-b border-border cursor-pointer transition-colors',
                    isSelected ? 'bg-secondary' : 'hover:bg-secondary/50'
                  )}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-medium text-sm">{draft.to}</span>
                    <span className="text-xs text-muted-foreground">{draft.createdAt}</span>
                  </div>
                  <div className="text-sm mb-1.5 line-clamp-1">{draft.subject}</div>
                  <div className="flex items-center gap-2">
                    <span
                      className={cn(
                        'text-[10px] font-medium px-2 py-0.5 rounded-full border',
                        config.color
                      )}
                    >
                      {config.label}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Draft Detail */}
        {selectedDraft ? (
          <div className="flex-1 flex flex-col">
            {/* Draft Header */}
            <div className="p-6 border-b border-border">
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="text-lg font-semibold mb-1">{selectedDraft.subject}</h2>
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <span>To: {selectedDraft.to}</span>
                    <span>&lt;{selectedDraft.toEmail}&gt;</span>
                  </div>
                </div>
                <div
                  className={cn(
                    'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border',
                    statusConfig[selectedDraft.status].color
                  )}
                >
                  {(() => {
                    const Icon = statusConfig[selectedDraft.status].icon;
                    return <Icon className="h-3.5 w-3.5" />;
                  })()}
                  {statusConfig[selectedDraft.status].label}
                </div>
              </div>

              {/* Context */}
              <div className="mt-4 p-3 rounded-lg bg-secondary/50 border border-border">
                <p className="text-xs text-muted-foreground mb-1">AI Context</p>
                <p className="text-sm">{selectedDraft.context}</p>
              </div>
            </div>

            {/* Draft Body */}
            <div className="flex-1 p-6 overflow-auto">
              <div className="prose prose-sm max-w-none">
                <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed">
                  {selectedDraft.body}
                </pre>
              </div>
            </div>

            {/* Actions */}
            {selectedDraft.status === 'pending' && (
              <div className="p-4 border-t border-border flex items-center gap-3">
                <button
                  onClick={() => handleApprove(selectedDraft.id)}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground font-medium text-sm hover:bg-primary/90 transition-colors"
                >
                  <Send className="h-4 w-4" />
                  Approve & Send
                </button>
                <button className="flex items-center gap-2 px-4 py-2 rounded-lg border border-input font-medium text-sm hover:bg-secondary transition-colors">
                  <Edit3 className="h-4 w-4" />
                  Edit Draft
                </button>
                <button
                  onClick={() => handleReject(selectedDraft.id)}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg border border-input font-medium text-sm text-destructive hover:bg-destructive/10 transition-colors"
                >
                  <XCircle className="h-4 w-4" />
                  Reject
                </button>
              </div>
            )}
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center text-muted-foreground">
            <div className="text-center">
              <Mail className="h-12 w-12 mx-auto mb-3 opacity-50" />
              <p>Select a draft to review</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
