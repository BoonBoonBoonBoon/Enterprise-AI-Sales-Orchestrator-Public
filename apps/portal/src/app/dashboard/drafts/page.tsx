'use client';

import { useEffect, useState } from 'react';
import { Header } from '@/components/layout/header';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  Clock,
  CheckCircle,
  XCircle,
  Edit3,
  Send,
  ChevronDown,
  ChevronUp,
  User,
  Building2,
  MessageSquare,
  Sparkles,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { fetchWithAuth } from '@/lib/api';

type DraftContext = {
  from_: string;
  content: string;
  date: string;
};

type DraftLead = {
  name: string;
  company?: string;
  role?: string;
  email?: string;
};

type Draft = {
  id: string;
  from_email: string;
  from_name: string;
  subject: string;
  mailbox: string;
  status: 'pending' | 'approved' | 'rejected' | 'sent' | 'failed';
  received_at: string;
  lead?: DraftLead;
  context: DraftContext[];
  draft_content: string;
  correlation_id: string;
};

type DraftListResponse = {
  drafts: Draft[];
  total: number;
  page: number;
  page_size: number;
};

const statusLabelMap: Record<Draft['status'], string> = {
  pending: 'Pending',
  approved: 'Approved',
  rejected: 'Rejected',
  sent: 'Sent',
  failed: 'Failed',
};

const statusClassMap: Record<Draft['status'], string> = {
  pending: 'bg-yellow-500/10 text-yellow-500',
  approved: 'bg-green-500/10 text-green-500',
  rejected: 'bg-red-500/10 text-red-500',
  sent: 'bg-green-500/10 text-green-500',
  failed: 'bg-red-500/10 text-red-500',
};

export default function DraftsPage() {
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [expandedDraft, setExpandedDraft] = useState<string | null>(null);
  const [editingContent, setEditingContent] = useState<{ [key: string]: string }>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadDrafts = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetchWithAuth('/api/v1/drafts');
      if (!res.ok) {
        throw new Error('Failed to load drafts');
      }
      const data = (await res.json()) as DraftListResponse;
      setDrafts(data.drafts ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load drafts');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDrafts();
  }, []);

  useEffect(() => {
    if (!expandedDraft && drafts.length > 0) {
      setExpandedDraft(drafts[0].id);
    }
  }, [drafts, expandedDraft]);

  const toggleExpand = (id: string) => {
    setExpandedDraft(expandedDraft === id ? null : id);
  };

  const handleContentChange = (id: string, content: string) => {
    setEditingContent({ ...editingContent, [id]: content });
  };

  const getContent = (draft: Draft) => {
    return editingContent[draft.id] !== undefined ? editingContent[draft.id] : draft.draft_content;
  };

  const handleApprove = async (draft: Draft) => {
    const content = getContent(draft);
    await fetchWithAuth(`/api/v1/drafts/${draft.id}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    });
    await loadDrafts();
  };

  const handleRewrite = async (draft: Draft) => {
    await fetchWithAuth(`/api/v1/drafts/${draft.id}/rewrite`, { method: 'POST' });
    await loadDrafts();
  };

  return (
    <div className="flex flex-col h-full">
      <Header title="Drafts" description="Review and approve AI-generated replies" />

      <div className="flex-1 p-6 overflow-auto">
        <div className="max-w-4xl mx-auto space-y-4">
          {/* Status bar */}
          <div className="flex items-center gap-4 p-4 rounded-lg border border-border/60 bg-muted/20">
            <div className="flex items-center gap-2">
              <div className="h-2 w-2 rounded-full bg-yellow-500 animate-pulse" />
              <span className="text-sm font-medium">
                {drafts.length} drafts pending approval
              </span>
            </div>
            <div className="flex-1" />
            <Button variant="outline" size="sm">
              Approve All
            </Button>
          </div>

          {/* Draft list */}
          {loading && (
            <div className="p-6 text-center text-muted-foreground">Loading drafts…</div>
          )}
          {error && (
            <div className="p-6 text-center text-destructive">{error}</div>
          )}
          {!loading && !error && drafts.map((draft) => (
            <Card
              key={draft.id}
              className={cn(
                'overflow-hidden transition-all',
                expandedDraft === draft.id && 'ring-2 ring-primary/50'
              )}
            >
              {/* Header */}
              <div
                className="flex items-start gap-4 p-4 cursor-pointer hover:bg-muted/30 transition-colors"
                onClick={() => toggleExpand(draft.id)}
              >
                <div className="h-10 w-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-white text-sm font-medium flex-shrink-0">
                  {draft.from_name
                    .split(' ')
                    .map((n) => n[0])
                    .join('')}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-medium">{draft.from_name}</span>
                    <span className="text-sm text-muted-foreground">&lt;{draft.from_email}&gt;</span>
                    <span
                      className={cn(
                        'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
                        statusClassMap[draft.status]
                      )}
                    >
                      <Clock className="h-3 w-3 mr-1" />
                      {statusLabelMap[draft.status]}
                    </span>
                  </div>
                  <p className="text-sm font-medium mt-0.5">{draft.subject}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    via {draft.mailbox} · {new Date(draft.received_at).toLocaleTimeString()}
                  </p>
                </div>
                <Button variant="ghost" size="icon" className="flex-shrink-0">
                  {expandedDraft === draft.id ? (
                    <ChevronUp className="h-5 w-5" />
                  ) : (
                    <ChevronDown className="h-5 w-5" />
                  )}
                </Button>
              </div>

              {/* Expanded content */}
              {expandedDraft === draft.id && (
                <CardContent className="pt-0 space-y-4">
                  {/* Lead info */}
                  <div className="flex items-center gap-4 p-3 rounded-lg bg-muted/30 border border-border/40">
                    <div className="flex items-center gap-2 text-sm">
                      <User className="h-4 w-4 text-muted-foreground" />
                      <span>{draft.lead?.name ?? 'Unknown lead'}</span>
                    </div>
                    <div className="flex items-center gap-2 text-sm">
                      <Building2 className="h-4 w-4 text-muted-foreground" />
                      <span>{draft.lead?.company ?? 'Unknown company'}</span>
                    </div>
                    <div className="text-sm text-muted-foreground">{draft.lead?.role ?? 'Role unknown'}</div>
                  </div>

                  {/* Conversation context */}
                  <div className="space-y-2">
                    <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                      <MessageSquare className="h-4 w-4" />
                      Conversation Context
                    </div>
                    <div className="space-y-2 p-3 rounded-lg bg-muted/20 border border-border/40 max-h-40 overflow-y-auto">
                      {(draft.context ?? []).map((msg, i) => (
                        <div key={i} className="text-sm">
                          <span
                            className={cn(
                              'font-medium',
                              msg.from_ === 'you' ? 'text-primary' : 'text-foreground'
                            )}
                          >
                            {msg.from_ === 'you' ? 'You' : draft.from_name}
                          </span>
                          <span className="text-muted-foreground"> · {msg.date}</span>
                          <p className="text-muted-foreground mt-0.5 line-clamp-2">{msg.content}</p>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Draft content */}
                  <div className="space-y-2">
                    <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                      <Sparkles className="h-4 w-4 text-primary" />
                      AI-Generated Draft
                    </div>
                    <textarea
                      className="w-full min-h-[200px] p-4 rounded-lg bg-background border border-border/60 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-ring"
                      value={getContent(draft)}
                      onChange={(e) => handleContentChange(draft.id, e.target.value)}
                    />
                  </div>

                  {/* Trace info */}
                  <div className="text-xs text-muted-foreground font-mono">
                    correlation_id: {draft.correlation_id}
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-3 pt-2 border-t border-border/40">
                    <Button variant="glow" className="gap-2" onClick={() => handleApprove(draft)}>
                      <Send className="h-4 w-4" />
                      Approve & Send
                    </Button>
                    <Button variant="outline" className="gap-2" onClick={() => handleRewrite(draft)}>
                      <Edit3 className="h-4 w-4" />
                      Request Rewrite
                    </Button>
                    <div className="flex-1" />
                    <Button variant="ghost" className="gap-2 text-destructive hover:text-destructive">
                      <XCircle className="h-4 w-4" />
                      Reject
                    </Button>
                  </div>
                </CardContent>
              )}
            </Card>
          ))}

          {!loading && !error && drafts.length === 0 && (
            <div className="text-center py-12">
              <CheckCircle className="h-12 w-12 mx-auto text-green-500 mb-4" />
              <h3 className="text-lg font-medium">All caught up!</h3>
              <p className="text-sm text-muted-foreground mt-1">No drafts pending approval.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
