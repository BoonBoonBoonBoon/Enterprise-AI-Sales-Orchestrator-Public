'use client';

import { useEffect, useMemo, useState, useCallback, useRef, type ChangeEvent, type FormEvent } from 'react';
import { Header } from '@/components/layout';
import {
  Search,
  Building2,
  Mail,
  Phone,
  MapPin,
  Globe,
  Linkedin,
  Sparkles,
  Flame,
  CheckCircle2,
  Clock,
  FileText,
  MessageSquare,
  ListTodo,
  DollarSign,
  Star,
  Calendar,
  User,
  Download,
  ExternalLink,
  TrendingUp,
  Target,
  Briefcase,
  ChevronRight,
  MoreHorizontal,
  Plus,
  Filter,
  Send,
  Bot,
  Loader2,
  RefreshCw,
  ChevronDown,
  AlertCircle,
} from 'lucide-react';
import { cn } from '@/lib/utils';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

type LeadTier = 'hot' | 'qualified' | 'potential';

type DbLead = {
  id: string;
  client_id: string;
  campaign_id: string;
  email: string;
  first_name: string;
  last_name: string;
  company_name: string;
  job_title: string;
  phone_number: string;
  current_status: string;
  sequence_step: number;
  sequence_active: boolean;
  next_action_date: string;
  last_contact_date: string;
  booking_status: string;
  lead_score: number | null;
  qualification_status: string | null;
  last_reply_sentiment: string | null;
  created_at: string;
  updated_at: string;
};

type DbStagingLead = {
  id: string;
  client_id: string;
  campaign_id: string;
  source: string;
  email: string | null;
  first_name: string | null;
  last_name: string | null;
  company_name: string | null;
  job_title: string | null;
  phone_number: string | null;
  linkedin_url: string | null;
  website_url: string | null;
  location: string | null;
  industry: string | null;
  company_size: string | null;
  revenue_range: string | null;
  enrichment_status: string;
  qualification_status: string;
  promotion_ready: boolean;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
};

type DbConversation = {
  id: string;
  lead_id: string;
  channel: string;
  status: string;
  summary: string;
  subject: string | null;
  created_at: string;
  updated_at: string;
};

type DbMessage = {
  id: string;
  conversation_id: string;
  sender_type: string;
  text_content: string;
  sent_at: string;
  created_at: string;
};

// Unified Lead type for UI
type Lead = {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  avatar_url?: string;
  company_name: string;
  job_title: string;
  phone_number?: string;
  location?: string;
  industry?: string;
  company_size?: string;
  website_url?: string;
  linkedin_url?: string;
  tier: LeadTier;
  lead_score: number;
  deal_value?: number;
  total_revenue?: number;
  satisfaction_rating?: number;
  current_status: string;
  last_contacted?: string;
  next_action_date?: string;
  account_manager?: string;
  ai_summary?: string;
  tags?: string[];
  pain_points?: string[];
  interests?: string[];
  buying_intent?: string[];
  files?: { name: string; type: string; url: string }[];
  tasks?: { id: string; title: string; status: 'todo' | 'in_progress' | 'done'; due_date?: string }[];
  conversations?: { id: string; subject: string; last_message: string; date: string; unread?: boolean }[];
  created_at: string;
  source: 'leads' | 'staging';
  enrichment_status?: string;
  qualification_db_status?: string;
};

type MontyMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
};

type MontyConversation = {
  id: string;
  status: 'open' | 'closed';
  created_at: string;
  ended_at?: string | null;
  title?: string | null;
  message_count?: number;
  is_legacy?: boolean;
};

type ConversationMessage = {
  id: string;
  sender: 'agent' | 'lead' | 'unknown';
  content: string;
  sent_at: string;
};

// ─────────────────────────────────────────────────────────────────────────────
// Data Fetching
// ─────────────────────────────────────────────────────────────────────────────

function determineTier(lead: DbLead | DbStagingLead, source: 'leads' | 'staging'): LeadTier {
  // As requested: leads table => qualified, staging_leads => potential
  if (source === 'leads') return 'qualified';
  return 'potential';
}

function transformDbLeadToLead(dbLead: DbLead, conversations: DbConversation[]): Lead {
  const tier = determineTier(dbLead, 'leads');
  const leadConversations = conversations
    .filter(c => c.lead_id === dbLead.id)
    .map(c => ({
      id: c.id,
      subject: c.subject || 'Conversation',
      last_message: c.summary || 'No summary available',
      date: c.updated_at,
      unread: false,
    }));

  return {
    id: dbLead.id,
    email: dbLead.email,
    first_name: dbLead.first_name,
    last_name: dbLead.last_name,
    company_name: dbLead.company_name,
    job_title: dbLead.job_title,
    phone_number: dbLead.phone_number || undefined,
    tier,
    lead_score: dbLead.lead_score ?? 50,
    current_status: dbLead.current_status,
    last_contacted: dbLead.last_contact_date || undefined,
    next_action_date: dbLead.next_action_date || undefined,
    conversations: leadConversations.length > 0 ? leadConversations : undefined,
    created_at: dbLead.created_at,
    source: 'leads',
    qualification_db_status: dbLead.qualification_status || undefined,
    ai_summary: dbLead.last_reply_sentiment 
      ? `Last reply sentiment: ${dbLead.last_reply_sentiment}. Currently in ${dbLead.current_status} stage.`
      : `Lead is currently in ${dbLead.current_status} stage with booking status: ${dbLead.booking_status}.`,
    tags: [dbLead.current_status, dbLead.booking_status].filter(Boolean),
  };
}

function transformStagingLeadToLead(stagingLead: DbStagingLead, conversations: DbConversation[] = []): Lead {
  const tier = determineTier(stagingLead, 'staging');

  const leadConversations = conversations.map(c => ({
    id: c.id,
    subject: c.subject || 'Conversation',
    last_message: c.summary || 'No summary available',
    date: c.updated_at,
    unread: false,
  }));
  
  return {
    id: stagingLead.id,
    email: stagingLead.email || 'No email',
    first_name: stagingLead.first_name || 'Unknown',
    last_name: stagingLead.last_name || '',
    company_name: stagingLead.company_name || 'Unknown Company',
    job_title: stagingLead.job_title || 'Unknown Role',
    phone_number: stagingLead.phone_number || undefined,
    location: stagingLead.location || undefined,
    industry: stagingLead.industry || undefined,
    company_size: stagingLead.company_size || undefined,
    website_url: stagingLead.website_url || undefined,
    linkedin_url: stagingLead.linkedin_url || undefined,
    tier,
    lead_score: stagingLead.promotion_ready ? 70 : (stagingLead.enrichment_status === 'enriched' ? 55 : 30),
    current_status: stagingLead.qualification_status,
    conversations: leadConversations.length > 0 ? leadConversations : undefined,
    created_at: stagingLead.created_at,
    source: 'staging',
    enrichment_status: stagingLead.enrichment_status,
    qualification_db_status: stagingLead.qualification_status,
    ai_summary: `Source: ${stagingLead.source}. Enrichment: ${stagingLead.enrichment_status}. ${stagingLead.promotion_ready ? 'Ready for promotion to qualified lead.' : 'Pending qualification review.'}`,
    tags: [stagingLead.source, stagingLead.enrichment_status, stagingLead.industry].filter(Boolean) as string[],
  };
}

type ProspectsApiResponse = {
  data: (DbLead | DbStagingLead)[];
  conversations: Record<string, DbConversation[]>;
};

async function fetchProspects(dataset: 'staging' | 'qualified'): Promise<ProspectsApiResponse> {
  const res = await fetch(`/api/prospects?dataset=${dataset}`, { cache: 'no-store' });
  if (!res.ok) {
    const errorPayload = await res.json().catch(() => ({}));
    throw new Error(errorPayload?.error || `Failed to fetch ${dataset} prospects`);
  }
  const payload = await res.json();
  return {
    data: payload?.data ?? [],
    conversations: payload?.conversations ?? {},
  };
}

async function fetchLeadsData(): Promise<{ leads: Lead[]; error: string | null }> {
  try {
    const [qualifiedRes, stagingRes] = await Promise.all([
      fetchProspects('qualified'),
      fetchProspects('staging'),
    ]);

    const qualifiedLeads = (qualifiedRes.data as DbLead[]).map((l) =>
      transformDbLeadToLead(l, qualifiedRes.conversations[l.id] ?? [])
    );
    const stagingLeads = (stagingRes.data as DbStagingLead[])
      .filter((l) => !('archived_at' in l) || !(l as DbStagingLead).archived_at)
      .map((l) => transformStagingLeadToLead(l, stagingRes.conversations[l.id] ?? []));

    const allLeads = [...qualifiedLeads, ...stagingLeads].sort((a, b) => {
      const tierOrder = { hot: 0, qualified: 1, potential: 2 };
      return tierOrder[a.tier] - tierOrder[b.tier];
    });

    return { leads: allLeads, error: null };
  } catch (err) {
    console.error('Error fetching leads:', err);
    return { leads: [], error: err instanceof Error ? err.message : 'Failed to fetch leads' };
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function getInitials(firstName?: string, lastName?: string, email?: string): string {
  if (firstName && lastName) {
    return `${firstName[0]}${lastName[0]}`.toUpperCase();
  }
  if (firstName) return firstName.slice(0, 2).toUpperCase();
  if (email) return email.slice(0, 2).toUpperCase();
  return '??';
}

function formatCurrency(value?: number): string {
  if (!value) return '—';
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value);
}

function formatDate(dateStr?: string): string {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: '2-digit' });
}

function getRelativeTime(dateStr?: string): string {
  if (!dateStr) return '—';
  const date = new Date(dateStr);
  const now = new Date();
  const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));
  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays} days ago`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
  return formatDate(dateStr);
}

const tierConfig: Record<LeadTier, { label: string; icon: typeof Flame; color: string; bgColor: string }> = {
  hot: { label: 'Hot Lead', icon: Flame, color: 'text-orange-600', bgColor: 'bg-orange-500/10' },
  qualified: { label: 'Qualified', icon: CheckCircle2, color: 'text-emerald-600', bgColor: 'bg-emerald-500/10' },
  potential: { label: 'Potential', icon: Target, color: 'text-blue-600', bgColor: 'bg-blue-500/10' },
};

// ─────────────────────────────────────────────────────────────────────────────
// Components
// ─────────────────────────────────────────────────────────────────────────────

type ProfileTab = 'overview' | 'tasks' | 'conversations';

function LeadCard({ lead, isSelected, onClick }: { lead: Lead; isSelected: boolean; onClick: () => void }) {
  const tier = tierConfig[lead.tier];
  const TierIcon = tier.icon;

  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full text-left p-4 transition-all duration-200 border-l-4',
        isSelected
          ? 'bg-primary/5 border-l-primary'
          : 'bg-transparent border-l-transparent hover:bg-secondary/50'
      )}
    >
      <div className="flex items-start gap-3">
        {/* Avatar */}
        <div className="relative shrink-0">
          {lead.avatar_url ? (
            <img
              src={lead.avatar_url}
              alt={`${lead.first_name} ${lead.last_name}`}
              className="w-12 h-12 rounded-xl object-cover"
            />
          ) : (
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-primary/20 to-primary/5 flex items-center justify-center text-primary font-semibold">
              {getInitials(lead.first_name, lead.last_name, lead.email)}
            </div>
          )}
          {/* Tier indicator dot */}
          <div className={cn('absolute -bottom-1 -right-1 w-4 h-4 rounded-full border-2 border-card flex items-center justify-center', tier.bgColor)}>
            <TierIcon className={cn('w-2.5 h-2.5', tier.color)} />
          </div>
        </div>

        {/* Info */}
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <div className="font-semibold text-sm truncate">{lead.first_name} {lead.last_name}</div>
              <div className="text-xs text-muted-foreground truncate">{lead.job_title}</div>
            </div>
            {lead.lead_score && (
              <div className={cn('shrink-0 px-2 py-0.5 rounded-full text-xs font-bold', tier.bgColor, tier.color)}>
                {lead.lead_score}
              </div>
            )}
          </div>

          <div className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground">
            <Building2 className="w-3.5 h-3.5" />
            <span className="truncate">{lead.company_name}</span>
          </div>

          {lead.deal_value && (
            <div className="mt-1.5 flex items-center gap-1.5 text-xs font-medium text-emerald-600">
              <DollarSign className="w-3.5 h-3.5" />
              {formatCurrency(lead.deal_value)}
            </div>
          )}

          <div className="mt-2 flex items-center gap-2">
            <span className={cn('px-2 py-0.5 rounded-full text-[10px] font-medium', tier.bgColor, tier.color)}>
              {tier.label}
            </span>
            {lead.industry && (
              <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-secondary text-secondary-foreground">
                {lead.industry}
              </span>
            )}
          </div>
        </div>
      </div>
    </button>
  );
}

function StarRating({ rating }: { rating: number }) {
  const fullStars = Math.floor(rating);
  const hasHalf = rating % 1 >= 0.5;
  
  return (
    <div className="flex items-center gap-0.5">
      {[...Array(5)].map((_, i) => (
        <Star
          key={i}
          className={cn(
            'w-4 h-4',
            i < fullStars
              ? 'fill-amber-400 text-amber-400'
              : i === fullStars && hasHalf
              ? 'fill-amber-400/50 text-amber-400'
              : 'text-muted-foreground/30'
          )}
        />
      ))}
    </div>
  );
}

function TaskItem({ task }: { task: NonNullable<Lead['tasks']>[0] }) {
  const statusConfig = {
    todo: { label: 'To Do', color: 'text-muted-foreground', bg: 'bg-secondary' },
    in_progress: { label: 'In Progress', color: 'text-blue-600', bg: 'bg-blue-500/10' },
    done: { label: 'Done', color: 'text-emerald-600', bg: 'bg-emerald-500/10' },
  };
  const status = statusConfig[task.status];

  return (
    <div className="flex items-center gap-3 p-3 rounded-xl border border-border bg-background hover:bg-secondary/30 transition-colors">
      <div className={cn('w-2 h-2 rounded-full', task.status === 'done' ? 'bg-emerald-500' : task.status === 'in_progress' ? 'bg-blue-500' : 'bg-muted-foreground/30')} />
      <div className="flex-1 min-w-0">
        <div className={cn('text-sm font-medium', task.status === 'done' && 'line-through text-muted-foreground')}>{task.title}</div>
        {task.due_date && (
          <div className="text-xs text-muted-foreground mt-0.5">Due: {formatDate(task.due_date)}</div>
        )}
      </div>
      <span className={cn('px-2 py-0.5 rounded-full text-[10px] font-medium', status.bg, status.color)}>
        {status.label}
      </span>
    </div>
  );
}

function ConversationItem({
  conversation,
  isExpanded,
  isLoading,
  messages,
  onToggle,
}: {
  conversation: NonNullable<Lead['conversations']>[0];
  isExpanded: boolean;
  isLoading: boolean;
  messages: ConversationMessage[];
  onToggle: () => void;
}) {
  return (
    <div
      className={cn(
        'rounded-xl border border-border bg-background transition-colors',
        conversation.unread && 'border-l-4 border-l-primary'
      )}
    >
      <button
        type="button"
        onClick={onToggle}
        className={cn(
          'w-full text-left p-4 hover:bg-secondary/30 transition-colors cursor-pointer',
          isExpanded && 'bg-secondary/20'
        )}
      >
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className={cn('text-sm font-medium truncate', conversation.unread && 'font-semibold')}>{conversation.subject}</span>
              {conversation.unread && (
                <span className="w-2 h-2 rounded-full bg-primary shrink-0" />
              )}
            </div>
            <div className="text-xs text-muted-foreground mt-1 truncate">{conversation.last_message}</div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span className="text-xs text-muted-foreground">{getRelativeTime(conversation.date)}</span>
            <ChevronDown className={cn('w-4 h-4 text-muted-foreground transition-transform', isExpanded && 'rotate-180')} />
          </div>
        </div>
      </button>

      {isExpanded && (
        <div className="border-t border-border px-4 py-3 bg-background/60">
          {isLoading ? (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              Loading messages...
            </div>
          ) : messages.length > 0 ? (
            <div className="space-y-3">
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={cn('flex', msg.sender === 'agent' ? 'justify-end' : 'justify-start')}
                >
                  <div
                    className={cn(
                      'max-w-[85%] rounded-xl px-3 py-2 text-xs leading-relaxed',
                      msg.sender === 'agent' ? 'bg-primary text-primary-foreground' : 'bg-secondary'
                    )}
                  >
                    <div className="text-[10px] opacity-70 mb-1">
                      {msg.sender === 'agent' ? 'You' : msg.sender === 'lead' ? 'Prospect' : 'Unknown'} · {new Date(msg.sent_at).toLocaleString()}
                    </div>
                    {msg.content}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-xs text-muted-foreground">No messages in this conversation yet.</div>
          )}
        </div>
      )}
    </div>
  );
}

function FileItem({ file }: { file: NonNullable<Lead['files']>[0] }) {
  return (
    <div className="flex items-center gap-3 p-3 rounded-xl border border-border bg-background hover:bg-secondary/30 transition-colors group">
      <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
        <FileText className="w-5 h-5 text-primary" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium truncate">{file.name}</div>
        <div className="text-xs text-muted-foreground capitalize">{file.type}</div>
      </div>
      <button className="opacity-0 group-hover:opacity-100 p-2 rounded-lg hover:bg-secondary transition-all">
        <Download className="w-4 h-4 text-muted-foreground" />
      </button>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Monty Chat Component
// ─────────────────────────────────────────────────────────────────────────────

function MontyChat({
  lead,
  messages,
  messagesByConversation,
  setMessages,
  conversations,
  setConversations,
  activeConversationId,
  setActiveConversationId,
}: {
  lead: Lead;
  messages: MontyMessage[];
  messagesByConversation: Record<string, MontyMessage[]>;
  setMessages: (conversationId: string, updater: (prev: MontyMessage[]) => MontyMessage[]) => void;
  conversations: MontyConversation[];
  setConversations: (updater: (prev: MontyConversation[]) => MontyConversation[]) => void;
  activeConversationId: string | null;
  setActiveConversationId: (conversationId: string | null) => void;
}) {
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [rateLimit, setRateLimit] = useState<{ remaining: number; limit: number } | null>(null);
  const [copilotReady, setCopilotReady] = useState<boolean | null>(null);
  const [copilotReasons, setCopilotReasons] = useState<string[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    let cancelled = false;
    setCopilotReady(null);
    setCopilotReasons([]);
    fetch('/api/monty/health', { cache: 'no-store' })
      .then(async (res) => {
        const data = await res.json().catch(() => ({ ok: false, reasons: ['Health check failed'] }));
        if (cancelled) return;
        setCopilotReady(Boolean(data.ok));
        setCopilotReasons(Array.isArray(data.reasons) ? data.reasons : []);
      })
      .catch(() => {
        if (cancelled) return;
        setCopilotReady(false);
        setCopilotReasons(['Health check failed']);
      });
    return () => {
      cancelled = true;
    };
  }, [lead.id]);

  useEffect(() => {
    setInput('');
    setIsTyping(false);
    setApiError(null);
    setRateLimit(null);
  }, [lead.id]);

  useEffect(() => {
    setInput('');
    setApiError(null);
  }, [activeConversationId]);

  const loadChatHistory = useCallback(async (conversationId: string) => {
    try {
      const leadSource = lead.source === 'staging' ? 'staging_leads' : 'leads';
      const response = await fetch(
        `/api/monty/chat?leadId=${lead.id}&leadSource=${leadSource}&conversationId=${conversationId}&limit=50`,
        { cache: 'no-store' }
      );

      if (response.ok) {
        const data = await response.json();
        if (data.messages && data.messages.length > 0) {
          const loadedMessages: MontyMessage[] = data.messages.map((m: { id: string; role: 'user' | 'assistant'; content: string; created_at: string }) => ({
            id: m.id,
            role: m.role,
            content: m.content,
            timestamp: new Date(m.created_at),
          }));
          setMessages(conversationId, () => loadedMessages);
        } else {
          setMessages(conversationId, () => []);
        }
      }
    } catch (err) {
      console.error('Failed to load chat history:', err);
    }
  }, [lead.id, lead.source, setMessages]);

  const fetchConversations = useCallback(async () => {
    try {
      const leadSource = lead.source === 'staging' ? 'staging_leads' : 'leads';
      const response = await fetch(
        `/api/monty/chat/conversations?leadId=${lead.id}&leadSource=${leadSource}&limit=50`,
        { cache: 'no-store' }
      );

      if (response.ok) {
        const data = await response.json();
        const list = data.conversations ?? [];
        setConversations(() => list);
        return list as MontyConversation[];
      }
    } catch (err) {
      console.error('Failed to load chat conversations:', err);
    }
    return [] as MontyConversation[];
  }, [lead.id, lead.source, setConversations]);

  const startNewConversation = useCallback(async (options?: { silent?: boolean }): Promise<string | null> => {
    try {
      const leadSource = lead.source === 'staging' ? 'staging_leads' : 'leads';
      const response = await fetch('/api/monty/chat/conversations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ leadId: lead.id, leadSource }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.error || 'Failed to start new chat');
      }

      const data = await response.json();
      const conversation = data.conversation as MontyConversation;

      setConversations((prev) => [conversation, ...prev.filter(c => c.id !== conversation.id)]);
      setActiveConversationId(conversation.id);
      setMessages(conversation.id, () => []);
      setInput('');
      setIsTyping(false);
      setApiError(null);
      return conversation.id;
    } catch (err) {
      if (!options?.silent) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to start new chat';
        setApiError(errorMessage);
      }
      return null;
    }
  }, [lead.id, lead.source, setActiveConversationId, setConversations, setMessages]);

  // Initialize conversations and start a new session on lead change / refresh
  useEffect(() => {
    fetchConversations().then((list) => {
      if (list.length > 0) {
        setActiveConversationId(list[0].id);
        return;
      }
      startNewConversation({ silent: true });
    });
  }, [fetchConversations, setActiveConversationId, startNewConversation]);

  // Load messages when the active conversation changes
  useEffect(() => {
    if (!activeConversationId) return;
    const existing = messagesByConversation[activeConversationId];
    if (existing && existing.length > 0) return;
    loadChatHistory(activeConversationId);
  }, [activeConversationId, loadChatHistory, messagesByConversation]);

  const handleSubmit = useCallback(async (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isTyping) return;
    const resolvedConversationId = activeConversationId ?? (await startNewConversation());
    const conversationKey = resolvedConversationId ?? 'legacy';
    if (!resolvedConversationId) {
      setActiveConversationId('legacy');
    }

    const activeConversation = resolvedConversationId
      ? conversations.find(c => c.id === resolvedConversationId)
      : null;
    if (activeConversation?.status === 'closed') {
      setApiError('This conversation is closed. Start a new chat to continue.');
      return;
    }

    const userMessage: MontyMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    };

    setMessages(conversationKey, prev => [...prev, userMessage]);
    setInput('');
    setIsTyping(true);
    setApiError(null);

    try {
      // Build conversation history for context
      const conversationHistory = messages.map(m => ({
        role: m.role,
        content: m.content,
      }));

      const leadSource = lead.source === 'staging' ? 'staging_leads' : 'leads';
      
      const response = await fetch('/api/monty/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          leadId: lead.id,
          leadSource,
          message: userMessage.content,
          ...(resolvedConversationId ? { conversationId: resolvedConversationId } : {}),
          conversationHistory,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Failed to get AI response');
      }

      // Update rate limit info
      if (data.rateLimit) {
        setRateLimit(data.rateLimit);
      }

      const aiMessage: MontyMessage = {
        id: `ai-${Date.now()}`,
        role: 'assistant',
        content: data.message,
        timestamp: new Date(),
      };

      setMessages(conversationKey, prev => [...prev, aiMessage]);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Something went wrong';
      setApiError(errorMessage);
      
      // Add error message to chat
      const errorMsg: MontyMessage = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: `Sorry, I encountered an issue: ${errorMessage}. Please try again.`,
        timestamp: new Date(),
      };
      setMessages(conversationKey, prev => [...prev, errorMsg]);
    } finally {
      setIsTyping(false);
    }
  }, [activeConversationId, conversations, input, isTyping, lead, messages, setMessages, startNewConversation]);

  const quickPrompts = [
    'Give me a 30-second exec summary of this lead.',
    'What signals suggest interest (and what’s missing)?',
    'What’s the best next step + 2 options?',
    'Draft a short follow-up email (grounded in what we know).',
  ];

  return (
    <div className="flex flex-col h-full">
      {/* Chat Header */}
      <div className="flex items-center gap-3 p-4 border-b border-border">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">
          <Bot className="w-5 h-5 text-white" />
        </div>
        <div>
          <div className="font-semibold text-sm">Ask Monty</div>
          <div className="text-xs text-muted-foreground">AI insights about {lead.first_name}</div>
        </div>
        <div className="ml-auto">
          <button
            onClick={() => startNewConversation()}
            className="px-3 py-1.5 rounded-lg text-xs bg-secondary hover:bg-secondary/80 transition-colors"
          >
            New chat
          </button>
        </div>
      </div>

      {/* Conversation List - Collapsible cards */}
      <div className="border-b border-border bg-secondary/10 p-3">
        <div className="flex items-center justify-between mb-2">
          <div className="text-[11px] uppercase tracking-wide text-muted-foreground">
            Copilot Chats ({conversations.length}/5)
          </div>
        </div>
        <div className="space-y-2 max-h-48 overflow-auto">
          {conversations.length === 0 ? (
            <div className="text-xs text-muted-foreground py-2">No chats yet. Start a conversation!</div>
          ) : (
            conversations.map((conversation) => {
              const isActive = conversation.id === activeConversationId;
              const title = conversation.title || (conversation.is_legacy ? 'Previous chat' : 'New chat');
              const msgCount = conversation.message_count ?? 0;
              const dateLabel = getRelativeTime(conversation.created_at);

              return (
                <div
                  key={conversation.id}
                  className={cn(
                    'rounded-xl border transition-colors',
                    isActive 
                      ? 'border-primary/50 bg-primary/5' 
                      : 'border-border bg-background hover:bg-secondary/30'
                  )}
                >
                  <button
                    type="button"
                    onClick={() => setActiveConversationId(conversation.id)}
                    className="w-full text-left p-3 cursor-pointer"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className={cn(
                            'text-xs font-medium truncate',
                            isActive && 'text-primary'
                          )}>
                            {title}
                          </span>
                          {conversation.status === 'open' && (
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
                          )}
                        </div>
                        <div className="text-[10px] text-muted-foreground mt-0.5">
                          {msgCount} message{msgCount !== 1 ? 's' : ''}
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className="text-[10px] text-muted-foreground">{dateLabel}</span>
                        <ChevronRight className={cn(
                          'w-3 h-3 text-muted-foreground transition-transform',
                          isActive && 'rotate-90'
                        )} />
                      </div>
                    </div>
                  </button>
                </div>
              );
            })
          )}
        </div>
      </div>

      {activeConversationId && conversations.find(c => c.id === activeConversationId)?.status === 'closed' && (
        <div className="px-4 py-2 border-b border-border text-xs text-muted-foreground">
          Viewing a past conversation. Start a new chat to continue.
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 min-h-0 overflow-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-4">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-500/20 to-purple-600/20 flex items-center justify-center mb-4">
              <Sparkles className="w-8 h-8 text-violet-500" />
            </div>
            <p className="text-sm font-medium mb-1">Chat with Monty</p>
            <p className="text-xs text-muted-foreground mb-4">Get AI-powered insights about {lead.first_name}</p>
            <div className="flex flex-wrap justify-center gap-2">
              {quickPrompts.map((prompt) => (
                <button
                  key={prompt}
                  onClick={() => setInput(prompt)}
                  className="px-3 py-1.5 rounded-full text-xs bg-secondary hover:bg-secondary/80 transition-colors"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={cn(
                  'flex gap-3',
                  msg.role === 'user' ? 'justify-end' : 'justify-start'
                )}
              >
                {msg.role === 'assistant' && (
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center shrink-0">
                    <Bot className="w-4 h-4 text-white" />
                  </div>
                )}
                <div
                  className={cn(
                    'max-w-[80%] rounded-2xl px-4 py-2.5 text-sm',
                    msg.role === 'user'
                      ? 'bg-primary text-primary-foreground rounded-br-md'
                      : 'bg-secondary rounded-bl-md'
                  )}
                >
                  {msg.content}
                </div>
              </div>
            ))}
            {isTyping && (
              <div className="flex gap-3">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center shrink-0">
                  <Bot className="w-4 h-4 text-white" />
                </div>
                <div className="bg-secondary rounded-2xl rounded-bl-md px-4 py-2.5">
                  <div className="flex gap-1">
                    <span className="w-2 h-2 rounded-full bg-muted-foreground/50 animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="w-2 h-2 rounded-full bg-muted-foreground/50 animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="w-2 h-2 rounded-full bg-muted-foreground/50 animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Rate Limit Warning */}
      {rateLimit && rateLimit.remaining <= 10 && (
        <div className="px-4 py-2 bg-amber-500/10 border-t border-amber-500/20 text-xs text-amber-600">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-3 h-3" />
            {rateLimit.remaining === 0 
              ? 'Daily limit reached. Try again tomorrow.'
              : `${rateLimit.remaining} of ${rateLimit.limit} messages remaining today`
            }
          </div>
        </div>
      )}

      {copilotReady === false && (
        <div className="px-4 py-2 bg-destructive/10 border-t border-destructive/20 text-xs text-destructive">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-3 h-3" />
            Copilot unavailable. {copilotReasons.length > 0 ? copilotReasons.join(' · ') : 'Check configuration.'}
          </div>
        </div>
      )}

      {apiError && (
        <div className="px-4 py-2 bg-destructive/10 border-t border-destructive/20 text-xs text-destructive">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-3 h-3" />
            {apiError}
          </div>
        </div>
      )}

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-4 border-t border-border">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={rateLimit?.remaining === 0 ? 'Daily limit reached...' : 'Ask about this lead...'}
            className="flex-1 px-4 py-2.5 rounded-xl border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:bg-muted"
            disabled={isTyping || rateLimit?.remaining === 0 || Boolean(activeConversationId && conversations.find(c => c.id === activeConversationId)?.status === 'closed')}
          />
          <button
            type="submit"
            disabled={!input.trim() || isTyping || rateLimit?.remaining === 0 || Boolean(activeConversationId && conversations.find(c => c.id === activeConversationId)?.status === 'closed')}
            className="px-4 py-2.5 rounded-xl bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </form>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────

export default function LeadsPage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [selectedTier, setSelectedTier] = useState<LeadTier | 'all'>('all');
  const [selectedIndustry, setSelectedIndustry] = useState<string>('all');
  const [selectedLeadId, setSelectedLeadId] = useState<string>('');
  const [activeTab, setActiveTab] = useState<ProfileTab>('overview');
  const [showTierDropdown, setShowTierDropdown] = useState(false);
  const [montyChats, setMontyChats] = useState<Record<string, Record<string, MontyMessage[]>>>({});
  const [montyConversations, setMontyConversations] = useState<Record<string, MontyConversation[]>>({});
  const [montyActiveConversationId, setMontyActiveConversationId] = useState<Record<string, string | null>>({});
  const [expandedConversationId, setExpandedConversationId] = useState<string | null>(null);
  const [conversationMessages, setConversationMessages] = useState<Record<string, ConversationMessage[]>>({});
  const [loadingConversationId, setLoadingConversationId] = useState<string | null>(null);

  // Fetch leads on mount
  useEffect(() => {
    async function loadLeads() {
      setIsLoading(true);
      const { leads: fetchedLeads, error: fetchError } = await fetchLeadsData();
      setLeads(fetchedLeads);
      setError(fetchError);
      if (fetchedLeads.length > 0 && !selectedLeadId) {
        setSelectedLeadId(fetchedLeads[0].id);
      }
      setIsLoading(false);
    }
    loadLeads();
  }, []);

  const handleRefresh = useCallback(async () => {
    setIsLoading(true);
    const { leads: fetchedLeads, error: fetchError } = await fetchLeadsData();
    setLeads(fetchedLeads);
    setError(fetchError);
    setIsLoading(false);
  }, []);

  const industries = useMemo(() => {
    const set = new Set(leads.map((l) => l.industry).filter(Boolean));
    return ['all', ...Array.from(set)] as string[];
  }, [leads]);

  const filteredLeads = useMemo(() => {
    return leads.filter((lead) => {
      // Tier filter
      if (selectedTier !== 'all' && lead.tier !== selectedTier) return false;
      // Industry filter
      if (selectedIndustry !== 'all' && lead.industry !== selectedIndustry) return false;
      // Search
      if (query) {
        const q = query.toLowerCase();
        const searchable = `${lead.first_name} ${lead.last_name} ${lead.email} ${lead.company_name} ${lead.job_title} ${lead.industry ?? ''}`.toLowerCase();
        if (!searchable.includes(q)) return false;
      }
      return true;
    });
  }, [leads, query, selectedTier, selectedIndustry]);

  const selectedLead = useMemo(() => {
    return filteredLeads.find((l) => l.id === selectedLeadId) ?? filteredLeads[0] ?? null;
  }, [filteredLeads, selectedLeadId]);

  const selectedMontyMessages = useMemo(() => {
    if (!selectedLead) return [] as MontyMessage[];
    const key = `${selectedLead.source}:${selectedLead.id}`;
    const activeId = montyActiveConversationId[key];
    if (!activeId) return [] as MontyMessage[];
    return montyChats[key]?.[activeId] ?? [];
  }, [montyActiveConversationId, montyChats, selectedLead]);

  useEffect(() => {
    setExpandedConversationId(null);
  }, [selectedLeadId]);

  const loadConversationMessages = useCallback(async (conversationId: string) => {
    if (!selectedLead) return;
    if (conversationMessages[conversationId]) return;

    try {
      setLoadingConversationId(conversationId);
      const source = selectedLead.source === 'staging' ? 'staging' : 'leads';
      const res = await fetch(`/api/conversations/messages?conversationId=${conversationId}&source=${source}`, { cache: 'no-store' });
      if (!res.ok) {
        const errorPayload = await res.json().catch(() => ({}));
        throw new Error(errorPayload?.error || 'Failed to load messages');
      }
      const payload = await res.json();
      const messages = (payload?.messages ?? []) as ConversationMessage[];
      setConversationMessages((prev) => ({
        ...prev,
        [conversationId]: messages,
      }));
    } catch (err) {
      console.error('Failed to load conversation messages:', err);
      setConversationMessages((prev) => ({
        ...prev,
        [conversationId]: [],
      }));
    } finally {
      setLoadingConversationId(null);
    }
  }, [conversationMessages, selectedLead]);

  const handleToggleConversation = useCallback((conversationId: string) => {
    setExpandedConversationId((prev) => (prev === conversationId ? null : conversationId));
    loadConversationMessages(conversationId);
  }, [loadConversationMessages]);

  // Counts per tier
  const tierCounts = useMemo(() => ({
    all: leads.length,
    hot: leads.filter((l) => l.tier === 'hot').length,
    qualified: leads.filter((l) => l.tier === 'qualified').length,
    potential: leads.filter((l) => l.tier === 'potential').length,
  }), [leads]);

  const tierOptions = [
    { value: 'all' as const, label: 'All Leads', icon: null, count: tierCounts.all },
    { value: 'hot' as const, label: 'Hot Leads', icon: Flame, color: 'text-orange-600', count: tierCounts.hot },
    { value: 'qualified' as const, label: 'Qualified', icon: CheckCircle2, color: 'text-emerald-600', count: tierCounts.qualified },
    { value: 'potential' as const, label: 'Potential', icon: Target, color: 'text-blue-600', count: tierCounts.potential },
  ];

  const selectedTierOption = tierOptions.find(t => t.value === selectedTier) ?? tierOptions[0];

  return (
    <div className="flex flex-col h-full bg-background">
      <Header
        title="Prospects"
        description="Manage your deals, activities, and contacts in one place."
        backHref="/dashboard"
        backLabel="Back to Dashboard"
      />

      <div className="flex-1 p-6 overflow-hidden">
        <div className="h-full grid grid-cols-1 lg:grid-cols-[360px_1fr_340px] gap-6">
          
          {/* ═══════════════════════════════════════════════════════════════════
              LEFT: Lead List
              ═══════════════════════════════════════════════════════════════════ */}
          <div className="flex flex-col min-h-0 rounded-2xl border border-border bg-card overflow-hidden shadow-sm">
            {/* Header */}
            <div className="p-4 border-b border-border space-y-3">
              {/* Top Row: Tier Dropdown + Refresh */}
              <div className="flex items-center gap-2">
                {/* Tier Dropdown */}
                <div className="relative flex-1">
                  <button
                    onClick={() => setShowTierDropdown(!showTierDropdown)}
                    className="w-full flex items-center justify-between gap-2 px-4 py-2.5 rounded-xl border border-input bg-background hover:bg-secondary/50 transition-colors"
                  >
                    <div className="flex items-center gap-2">
                      {selectedTierOption.icon && (
                        <selectedTierOption.icon className={cn('w-4 h-4', selectedTierOption.color)} />
                      )}
                      <span className="text-sm font-medium">{selectedTierOption.label}</span>
                      <span className="px-1.5 py-0.5 rounded-full text-[10px] font-medium bg-primary/10 text-primary">
                        {selectedTierOption.count}
                      </span>
                    </div>
                    <ChevronDown className={cn('w-4 h-4 text-muted-foreground transition-transform', showTierDropdown && 'rotate-180')} />
                  </button>
                  
                  {showTierDropdown && (
                    <div className="absolute top-full left-0 right-0 mt-1 p-1 rounded-xl border border-border bg-card shadow-lg z-10">
                      {tierOptions.map((option) => (
                        <button
                          key={option.value}
                          onClick={() => {
                            setSelectedTier(option.value);
                            setShowTierDropdown(false);
                          }}
                          className={cn(
                            'w-full flex items-center justify-between gap-2 px-3 py-2 rounded-lg text-sm transition-colors',
                            selectedTier === option.value
                              ? 'bg-primary/10 text-primary'
                              : 'hover:bg-secondary'
                          )}
                        >
                          <div className="flex items-center gap-2">
                            {option.icon && <option.icon className={cn('w-4 h-4', option.color)} />}
                            <span>{option.label}</span>
                          </div>
                          <span className={cn(
                            'px-1.5 py-0.5 rounded-full text-[10px] font-medium',
                            selectedTier === option.value ? 'bg-primary/20' : 'bg-secondary'
                          )}>
                            {option.count}
                          </span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {/* Refresh Button */}
                <button
                  onClick={handleRefresh}
                  disabled={isLoading}
                  className="p-2.5 rounded-xl border border-input bg-background hover:bg-secondary/50 disabled:opacity-50 transition-colors"
                  title="Refresh leads"
                >
                  <RefreshCw className={cn('w-4 h-4 text-muted-foreground', isLoading && 'animate-spin')} />
                </button>
              </div>

              {/* Search */}
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <input
                  value={query}
                  onChange={(e: ChangeEvent<HTMLInputElement>) => setQuery(e.target.value)}
                  type="text"
                  placeholder="Search leads..."
                  className="pl-10 pr-4 py-2.5 w-full rounded-xl border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring transition-all"
                />
              </div>

              {/* Industry Filter */}
              <div className="flex items-center gap-2">
                <Filter className="w-4 h-4 text-muted-foreground shrink-0" />
                <select
                  value={selectedIndustry}
                  onChange={(e) => setSelectedIndustry(e.target.value)}
                  className="flex-1 px-3 py-2 rounded-lg border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  {industries.map((ind) => (
                    <option key={ind} value={ind}>
                      {ind === 'all' ? 'All Industries' : ind}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>{filteredLeads.length} leads</span>
                <button className="flex items-center gap-1 text-primary hover:underline">
                  <Plus className="w-3.5 h-3.5" />
                  Add Lead
                </button>
              </div>
            </div>

            {/* List */}
            <div className="flex-1 min-h-0 overflow-auto divide-y divide-border">
              {isLoading ? (
                <div className="flex flex-col items-center justify-center p-8 gap-3">
                  <Loader2 className="w-8 h-8 text-primary animate-spin" />
                  <span className="text-sm text-muted-foreground">Loading leads...</span>
                </div>
              ) : error ? (
                <div className="flex flex-col items-center justify-center p-8 gap-3 text-center">
                  <AlertCircle className="w-8 h-8 text-destructive" />
                  <div>
                    <p className="text-sm font-medium text-destructive">Failed to load leads</p>
                    <p className="text-xs text-muted-foreground mt-1">{error}</p>
                  </div>
                  <button
                    onClick={handleRefresh}
                    className="mt-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm hover:bg-primary/90 transition-colors"
                  >
                    Try Again
                  </button>
                </div>
              ) : filteredLeads.length === 0 ? (
                <div className="flex flex-col items-center justify-center p-8 gap-3 text-center">
                  <Target className="w-8 h-8 text-muted-foreground/50" />
                  <div>
                    <p className="text-sm font-medium">No leads found</p>
                    <p className="text-xs text-muted-foreground mt-1">
                      {leads.length === 0 
                        ? 'Start by adding prospects to your pipeline' 
                        : 'Try adjusting your filters'}
                    </p>
                  </div>
                </div>
              ) : (
                filteredLeads.map((lead) => (
                  <LeadCard
                    key={lead.id}
                    lead={lead}
                    isSelected={lead.id === selectedLead?.id}
                    onClick={() => setSelectedLeadId(lead.id)}
                  />
                ))
              )}
            </div>
          </div>

          {/* ═══════════════════════════════════════════════════════════════════
              CENTER: Lead Profile
              ═══════════════════════════════════════════════════════════════════ */}
          <div className="min-h-0 rounded-2xl border border-border bg-card overflow-hidden shadow-sm flex flex-col">
            {!selectedLead ? (
              <div className="h-full flex items-center justify-center p-6 text-muted-foreground">
                Select a lead to view their profile.
              </div>
            ) : (
              <>
                {/* Profile Header */}
                <div className="p-6 border-b border-border bg-gradient-to-br from-primary/5 to-transparent">
                  <div className="flex items-start gap-5">
                    {/* Large Avatar */}
                    <div className="relative shrink-0">
                      {selectedLead.avatar_url ? (
                        <img
                          src={selectedLead.avatar_url}
                          alt={`${selectedLead.first_name} ${selectedLead.last_name}`}
                          className="w-20 h-20 rounded-2xl object-cover shadow-lg"
                        />
                      ) : (
                        <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-primary to-primary/60 flex items-center justify-center text-primary-foreground font-bold text-xl shadow-lg">
                          {getInitials(selectedLead.first_name, selectedLead.last_name, selectedLead.email)}
                        </div>
                      )}
                      <div className={cn(
                        'absolute -bottom-2 -right-2 w-8 h-8 rounded-full border-4 border-card flex items-center justify-center shadow-sm',
                        tierConfig[selectedLead.tier].bgColor
                      )}>
                        {(() => {
                          const TierIcon = tierConfig[selectedLead.tier].icon;
                          return <TierIcon className={cn('w-4 h-4', tierConfig[selectedLead.tier].color)} />;
                        })()}
                      </div>
                    </div>

                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between">
                        <div>
                          <h2 className="text-xl font-bold">{selectedLead.first_name} {selectedLead.last_name}</h2>
                          <p className="text-sm text-muted-foreground mt-0.5">
                            {selectedLead.job_title} · {selectedLead.company_name}
                          </p>
                        </div>
                        <button className="p-2 rounded-lg hover:bg-secondary transition-colors">
                          <MoreHorizontal className="w-5 h-5 text-muted-foreground" />
                        </button>
                      </div>

                      {/* Tags */}
                      <div className="mt-3 flex flex-wrap gap-2">
                        <span className={cn('px-2.5 py-1 rounded-full text-xs font-medium flex items-center gap-1', tierConfig[selectedLead.tier].bgColor, tierConfig[selectedLead.tier].color)}>
                          {(() => {
                            const TierIcon = tierConfig[selectedLead.tier].icon;
                            return <TierIcon className="w-3.5 h-3.5" />;
                          })()}
                          {tierConfig[selectedLead.tier].label}
                        </span>
                        {selectedLead.tags?.map((tag) => (
                          <span key={tag} className="px-2.5 py-1 rounded-full text-xs font-medium bg-secondary text-secondary-foreground">
                            {tag}
                          </span>
                        ))}
                      </div>

                      {/* AI Summary */}
                      {selectedLead.ai_summary && (
                        <div className="mt-4 p-3 rounded-xl bg-primary/5 border border-primary/10">
                          <div className="flex items-center gap-1.5 text-xs font-medium text-primary mb-1">
                            <Sparkles className="w-3.5 h-3.5" />
                            AI Summary
                          </div>
                          <p className="text-sm text-muted-foreground leading-relaxed">{selectedLead.ai_summary}</p>
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Tabs */}
                <div className="flex border-b border-border">
                  {([
                    { key: 'overview' as const, label: 'Overview', icon: Briefcase, count: undefined as number | undefined },
                    { key: 'tasks' as const, label: 'Tasks', icon: ListTodo, count: selectedLead.tasks?.length },
                    { key: 'conversations' as const, label: 'Conversations', icon: MessageSquare, count: selectedLead.conversations?.length },
                  ]).map((tab) => (
                    <button
                      key={tab.key}
                      onClick={() => setActiveTab(tab.key)}
                      className={cn(
                        'flex-1 px-4 py-3 text-sm font-medium flex items-center justify-center gap-2 border-b-2 transition-colors',
                        activeTab === tab.key
                          ? 'border-primary text-primary'
                          : 'border-transparent text-muted-foreground hover:text-foreground'
                      )}
                    >
                      <tab.icon className="w-4 h-4" />
                      {tab.label}
                      {tab.count !== undefined && (
                        <span className={cn('px-1.5 py-0.5 rounded-full text-[10px]', activeTab === tab.key ? 'bg-primary/10' : 'bg-secondary')}>
                          {tab.count}
                        </span>
                      )}
                    </button>
                  ))}
                </div>

                {/* Tab Content */}
                <div className="flex-1 min-h-0 overflow-auto p-6 space-y-6">
                  {activeTab === 'overview' && (
                    <>
                      {/* Metrics Row */}
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                        <div className="p-4 rounded-xl border border-border bg-background">
                          <div className="flex items-center gap-2 text-muted-foreground text-xs mb-1">
                            <DollarSign className="w-3.5 h-3.5" />
                            Deal Value
                          </div>
                          <div className="text-lg font-bold text-emerald-600">{formatCurrency(selectedLead.deal_value)}</div>
                        </div>
                        <div className="p-4 rounded-xl border border-border bg-background">
                          <div className="flex items-center gap-2 text-muted-foreground text-xs mb-1">
                            <TrendingUp className="w-3.5 h-3.5" />
                            Total Revenue
                          </div>
                          <div className="text-lg font-bold">{formatCurrency(selectedLead.total_revenue)}</div>
                        </div>
                        <div className="p-4 rounded-xl border border-border bg-background">
                          <div className="flex items-center gap-2 text-muted-foreground text-xs mb-1">
                            <Target className="w-3.5 h-3.5" />
                            Lead Score
                          </div>
                          <div className="text-lg font-bold text-primary">{selectedLead.lead_score ?? '—'}</div>
                        </div>
                        <div className="p-4 rounded-xl border border-border bg-background">
                          <div className="flex items-center gap-2 text-muted-foreground text-xs mb-1">
                            <Star className="w-3.5 h-3.5" />
                            Satisfaction
                          </div>
                          {selectedLead.satisfaction_rating ? (
                            <StarRating rating={selectedLead.satisfaction_rating} />
                          ) : (
                            <div className="text-lg font-bold text-muted-foreground">—</div>
                          )}
                        </div>
                      </div>

                      {/* Contact Details */}
                      <div>
                        <h3 className="text-sm font-semibold mb-3">Contact Details</h3>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                          <div className="flex items-center gap-3 p-3 rounded-xl border border-border bg-background">
                            <Mail className="w-5 h-5 text-muted-foreground" />
                            <div className="min-w-0">
                              <div className="text-xs text-muted-foreground">Email</div>
                              <a href={`mailto:${selectedLead.email}`} className="text-sm font-medium text-primary hover:underline truncate block">
                                {selectedLead.email}
                              </a>
                            </div>
                          </div>
                          <div className="flex items-center gap-3 p-3 rounded-xl border border-border bg-background">
                            <Phone className="w-5 h-5 text-muted-foreground" />
                            <div className="min-w-0">
                              <div className="text-xs text-muted-foreground">Phone</div>
                              <div className="text-sm font-medium truncate">{selectedLead.phone_number ?? '—'}</div>
                            </div>
                          </div>
                          <div className="flex items-center gap-3 p-3 rounded-xl border border-border bg-background">
                            <MapPin className="w-5 h-5 text-muted-foreground" />
                            <div className="min-w-0">
                              <div className="text-xs text-muted-foreground">Location</div>
                              <div className="text-sm font-medium truncate">{selectedLead.location ?? '—'}</div>
                            </div>
                          </div>
                          <div className="flex items-center gap-3 p-3 rounded-xl border border-border bg-background">
                            <Linkedin className="w-5 h-5 text-muted-foreground" />
                            <div className="min-w-0">
                              <div className="text-xs text-muted-foreground">LinkedIn</div>
                              {selectedLead.linkedin_url ? (
                                <a href={selectedLead.linkedin_url} target="_blank" rel="noreferrer" className="text-sm font-medium text-primary hover:underline truncate block">
                                  View Profile <ExternalLink className="w-3 h-3 inline ml-1" />
                                </a>
                              ) : (
                                <div className="text-sm text-muted-foreground">—</div>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Company Info */}
                      <div>
                        <h3 className="text-sm font-semibold mb-3">Company Information</h3>
                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                          <div className="p-3 rounded-xl border border-border bg-background">
                            <div className="text-xs text-muted-foreground">Industry</div>
                            <div className="text-sm font-medium mt-0.5">{selectedLead.industry ?? '—'}</div>
                          </div>
                          <div className="p-3 rounded-xl border border-border bg-background">
                            <div className="text-xs text-muted-foreground">Company Size</div>
                            <div className="text-sm font-medium mt-0.5">{selectedLead.company_size ?? '—'}</div>
                          </div>
                          <div className="p-3 rounded-xl border border-border bg-background">
                            <div className="text-xs text-muted-foreground">Website</div>
                            {selectedLead.website_url ? (
                              <a href={selectedLead.website_url} target="_blank" rel="noreferrer" className="text-sm font-medium text-primary hover:underline truncate block mt-0.5">
                                {selectedLead.website_url.replace(/^https?:\/\//, '')}
                              </a>
                            ) : (
                              <div className="text-sm text-muted-foreground mt-0.5">—</div>
                            )}
                          </div>
                        </div>
                      </div>

                      {/* Pain Points & Interests */}
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div className="p-4 rounded-xl border border-border bg-background">
                          <h4 className="text-sm font-medium mb-3">Pain Points</h4>
                          <div className="flex flex-wrap gap-2">
                            {selectedLead.pain_points?.length ? (
                              selectedLead.pain_points.map((pp) => (
                                <span key={pp} className="px-2.5 py-1 rounded-full text-xs bg-red-500/10 text-red-600">{pp}</span>
                              ))
                            ) : (
                              <span className="text-sm text-muted-foreground">No pain points recorded.</span>
                            )}
                          </div>
                        </div>
                        <div className="p-4 rounded-xl border border-border bg-background">
                          <h4 className="text-sm font-medium mb-3">Interests</h4>
                          <div className="flex flex-wrap gap-2">
                            {selectedLead.interests?.length ? (
                              selectedLead.interests.map((int) => (
                                <span key={int} className="px-2.5 py-1 rounded-full text-xs bg-blue-500/10 text-blue-600">{int}</span>
                              ))
                            ) : (
                              <span className="text-sm text-muted-foreground">No interests recorded.</span>
                            )}
                          </div>
                        </div>
                      </div>

                      {/* Files */}
                      {selectedLead.files && selectedLead.files.length > 0 && (
                        <div>
                          <h3 className="text-sm font-semibold mb-3">Files & Documents</h3>
                          <div className="space-y-2">
                            {selectedLead.files.map((file) => (
                              <FileItem key={file.name} file={file} />
                            ))}
                          </div>
                        </div>
                      )}
                    </>
                  )}

                  {activeTab === 'tasks' && (
                    <div className="space-y-3">
                      {selectedLead.tasks && selectedLead.tasks.length > 0 ? (
                        selectedLead.tasks.map((task) => (
                          <TaskItem key={task.id} task={task} />
                        ))
                      ) : (
                        <div className="text-center text-muted-foreground py-8">
                          No tasks for this lead yet.
                        </div>
                      )}
                      <button className="w-full flex items-center justify-center gap-2 p-3 rounded-xl border-2 border-dashed border-border text-muted-foreground hover:border-primary hover:text-primary transition-colors">
                        <Plus className="w-4 h-4" />
                        Add Task
                      </button>
                    </div>
                  )}

                  {activeTab === 'conversations' && (
                    <div className="space-y-6">
                      {/* Monty Chat History */}
                      <div className="rounded-xl border border-border bg-background">
                        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
                          <div className="flex items-center gap-2 text-sm font-semibold">
                            <Bot className="w-4 h-4 text-violet-500" />
                            Monty Chat History
                          </div>
                          <span className="text-xs text-muted-foreground">
                            {selectedMontyMessages.length} messages
                          </span>
                        </div>
                        <div className="p-4 space-y-3 max-h-64 overflow-auto">
                          {selectedMontyMessages.length > 0 ? (
                            selectedMontyMessages.map((msg) => (
                              <div key={msg.id} className={cn('flex gap-2', msg.role === 'user' ? 'justify-end' : 'justify-start')}>
                                <div
                                  className={cn(
                                    'max-w-[80%] rounded-xl px-3 py-2 text-xs',
                                    msg.role === 'user'
                                      ? 'bg-primary text-primary-foreground'
                                      : 'bg-secondary'
                                  )}
                                >
                                  <div className="text-[10px] opacity-70 mb-1">
                                    {msg.role === 'user' ? 'You' : 'Monty'} · {msg.timestamp.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}
                                  </div>
                                  {msg.content}
                                </div>
                              </div>
                            ))
                          ) : (
                            <div className="text-center text-muted-foreground text-sm py-6">
                              No Monty chats yet. Use the panel on the right to start a conversation.
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Lead Conversations */}
                      <div className="space-y-3">
                        {selectedLead.conversations && selectedLead.conversations.length > 0 ? (
                          selectedLead.conversations.map((conv) => (
                            <ConversationItem
                              key={conv.id}
                              conversation={conv}
                              isExpanded={expandedConversationId === conv.id}
                              isLoading={loadingConversationId === conv.id}
                              messages={conversationMessages[conv.id] ?? []}
                              onToggle={() => handleToggleConversation(conv.id)}
                            />
                          ))
                        ) : (
                          <div className="text-center text-muted-foreground py-8">
                            No conversations with this lead yet.
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </>
            )}
          </div>

          {/* ═══════════════════════════════════════════════════════════════════
              RIGHT: Monty AI Chat + Quick Info
              ═══════════════════════════════════════════════════════════════════ */}
          <div className="hidden lg:flex flex-col min-h-0 rounded-2xl border border-border bg-card overflow-hidden shadow-sm">
            {selectedLead ? (
              <>
                {/* Quick Status Bar */}
                <div className="p-3 border-b border-border bg-secondary/30">
                  <div className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 font-medium">
                        {selectedLead.current_status}
                      </span>
                      {selectedLead.source === 'staging' && (
                        <span className="px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-600 font-medium">
                          Staging
                        </span>
                      )}
                    </div>
                    <span className="text-muted-foreground">Score: {selectedLead.lead_score}</span>
                  </div>
                  <div className="flex items-center justify-between text-xs mt-2 text-muted-foreground">
                    <span>Last: {getRelativeTime(selectedLead.last_contacted)}</span>
                    <span>Next: {formatDate(selectedLead.next_action_date)}</span>
                  </div>
                </div>

                {/* Monty Chat - Takes up most of the space */}
                <div className="flex-1 min-h-0">
                  <MontyChat
                    key={`${selectedLead.source}:${selectedLead.id}`}
                    lead={selectedLead}
                    messages={selectedMontyMessages}
                    messagesByConversation={montyChats[`${selectedLead.source}:${selectedLead.id}`] ?? {}}
                    conversations={montyConversations[`${selectedLead.source}:${selectedLead.id}`] ?? []}
                    activeConversationId={montyActiveConversationId[`${selectedLead.source}:${selectedLead.id}`] ?? null}
                    setActiveConversationId={(conversationId) =>
                      setMontyActiveConversationId((prev) => ({
                        ...prev,
                        [`${selectedLead.source}:${selectedLead.id}`]: conversationId,
                      }))
                    }
                    setConversations={(updater) =>
                      setMontyConversations((prev) => ({
                        ...prev,
                        [`${selectedLead.source}:${selectedLead.id}`]: updater(
                          prev[`${selectedLead.source}:${selectedLead.id}`] ?? []
                        ),
                      }))
                    }
                    setMessages={(conversationId, updater) =>
                      setMontyChats((prev) => ({
                        ...prev,
                        [`${selectedLead.source}:${selectedLead.id}`]: {
                          ...(prev[`${selectedLead.source}:${selectedLead.id}`] ?? {}),
                          [conversationId]: updater(
                            prev[`${selectedLead.source}:${selectedLead.id}`]?.[conversationId] ?? []
                          ),
                        },
                      }))
                    }
                  />
                </div>

                {/* Quick Actions */}
                <div className="p-3 border-t border-border space-y-2">
                  <button className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-xl bg-primary text-primary-foreground font-medium text-sm hover:bg-primary/90 transition-colors">
                    <Mail className="w-4 h-4" />
                    Send Email
                  </button>
                  <div className="flex gap-2">
                    <button className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg border border-input bg-background text-sm hover:bg-secondary/50 transition-colors">
                      <Phone className="w-3.5 h-3.5" />
                      Call
                    </button>
                    <button className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg border border-input bg-background text-sm hover:bg-secondary/50 transition-colors">
                      <Calendar className="w-3.5 h-3.5" />
                      Schedule
                    </button>
                  </div>
                </div>
              </>
            ) : (
              <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
                Select a lead
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
