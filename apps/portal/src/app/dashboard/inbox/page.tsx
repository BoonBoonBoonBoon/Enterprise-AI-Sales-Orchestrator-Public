'use client';

import { useEffect, useState } from 'react';
import { Header } from '@/components/layout/header';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Search, Mail, ChevronRight, Clock, CheckCircle, User } from 'lucide-react';
import { cn, formatRelativeTime } from '@/lib/utils';
import { fetchWithAuth } from '@/lib/api';

type ConversationListItem = {
  id: string;
  from_email: string;
  from_name: string;
  subject: string;
  mailbox: string;
  status: 'awaiting_reply' | 'replied' | 'closed';
  last_message_at: string;
  message_count: number;
  unread: boolean;
  preview?: string;
};

type ConversationMessage = {
  id: string;
  from_: string;
  content: string;
  timestamp: string;
};

type ConversationDetail = ConversationListItem & {
  messages: ConversationMessage[];
  lead_id?: string | null;
};

type ConversationListResponse = {
  conversations: ConversationListItem[];
  total: number;
  page: number;
  page_size: number;
};

export default function InboxPage() {
  const [conversations, setConversations] = useState<ConversationListItem[]>([]);
  const [selectedConversation, setSelectedConversation] = useState<string | null>(null);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  const loadConversations = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetchWithAuth('/api/v1/conversations');
      if (!res.ok) {
        throw new Error('Failed to load conversations');
      }
      const data = (await res.json()) as ConversationListResponse;
      setConversations(data.conversations ?? []);
      if (!selectedConversation && data.conversations?.length) {
        setSelectedConversation(data.conversations[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load conversations');
    } finally {
      setLoading(false);
    }
  };

  const loadConversationDetail = async (conversationId: string) => {
    try {
      setDetailLoading(true);
      const res = await fetchWithAuth(`/api/v1/conversations/${conversationId}`);
      if (!res.ok) {
        throw new Error('Failed to load conversation');
      }
      const data = (await res.json()) as ConversationDetail;
      setMessages(data.messages ?? []);
    } catch {
      setMessages([]);
    } finally {
      setDetailLoading(false);
    }
  };

  useEffect(() => {
    loadConversations();
  }, []);

  useEffect(() => {
    if (selectedConversation) {
      loadConversationDetail(selectedConversation);
    }
  }, [selectedConversation]);

  const filteredConversations = conversations.filter(
    (conv) =>
      conv.from_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      conv.subject.toLowerCase().includes(searchQuery.toLowerCase()) ||
      conv.from_email.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const selectedConv = conversations.find((c) => c.id === selectedConversation);

  return (
    <div className="flex flex-col h-full">
      <Header title="Inbox" description="View and manage email conversations" />

      <div className="flex-1 flex overflow-hidden">
        {/* Conversation list */}
        <div className="w-96 border-r border-border/60 flex flex-col">
          {/* Search */}
          <div className="p-4 border-b border-border/40">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search conversations..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 bg-muted/30"
              />
            </div>
          </div>

          {/* List */}
          <div className="flex-1 overflow-y-auto">
            {loading && (
              <div className="p-4 text-sm text-muted-foreground">Loading conversations…</div>
            )}
            {error && (
              <div className="p-4 text-sm text-destructive">{error}</div>
            )}
            {!loading && !error && filteredConversations.map((conv) => (
              <div
                key={conv.id}
                onClick={() => setSelectedConversation(conv.id)}
                className={cn(
                  'flex items-start gap-3 p-4 border-b border-border/40 cursor-pointer hover:bg-muted/30 transition-colors',
                  selectedConversation === conv.id && 'bg-muted/50',
                  conv.unread && 'bg-primary/5'
                )}
              >
                <div className="h-10 w-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-white text-sm font-medium flex-shrink-0">
                  {conv.from_name
                    .split(' ')
                    .map((n) => n[0])
                    .join('')}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className={cn('font-medium truncate', conv.unread && 'font-semibold')}>
                      {conv.from_name}
                    </span>
                    {conv.unread && <div className="h-2 w-2 rounded-full bg-primary flex-shrink-0" />}
                  </div>
                  <p className={cn('text-sm truncate', conv.unread ? 'text-foreground' : 'text-muted-foreground')}>
                    {conv.subject}
                  </p>
                  <p className="text-xs text-muted-foreground truncate mt-0.5">
                    {conv.preview ?? 'Open to view messages'}
                  </p>
                </div>
                <div className="text-xs text-muted-foreground whitespace-nowrap">
                  {formatRelativeTime(conv.last_message_at)}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Conversation detail */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {selectedConv ? (
            <>
              {/* Conversation header */}
              <div className="p-4 border-b border-border/40">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="font-semibold">{selectedConv.subject}</h2>
                    <p className="text-sm text-muted-foreground">
                      {selectedConv.from_name} &lt;{selectedConv.from_email}&gt; · via {selectedConv.mailbox}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {selectedConv.status === 'awaiting_reply' && (
                      <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-yellow-500/10 text-yellow-500">
                        <Clock className="h-3 w-3 mr-1" />
                        Awaiting Reply
                      </span>
                    )}
                    {selectedConv.status === 'replied' && (
                      <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-green-500/10 text-green-500">
                        <CheckCircle className="h-3 w-3 mr-1" />
                        Replied
                      </span>
                    )}
                    <Button variant="outline" size="sm">
                      View Lead
                      <ChevronRight className="h-4 w-4 ml-1" />
                    </Button>
                  </div>
                </div>
              </div>

              {/* Messages */}
              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {detailLoading && (
                  <div className="text-sm text-muted-foreground">Loading messages…</div>
                )}
                {!detailLoading && messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={cn('flex gap-3', msg.from_ === 'you' && 'flex-row-reverse')}
                  >
                    <div
                      className={cn(
                        'h-8 w-8 rounded-full flex items-center justify-center text-xs font-medium flex-shrink-0',
                        msg.from_ === 'you'
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-gradient-to-br from-blue-500 to-purple-500 text-white'
                      )}
                    >
                      {msg.from_ === 'you'
                        ? 'You'
                        : selectedConv.from_name.split(' ').map((n) => n[0]).join('')}
                    </div>
                    <div
                      className={cn(
                        'max-w-[70%] rounded-lg p-4',
                        msg.from_ === 'you'
                          ? 'bg-primary/10 border border-primary/20'
                          : 'bg-muted/50 border border-border/40'
                      )}
                    >
                      <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                      <p className="text-xs text-muted-foreground mt-2">
                        {new Date(msg.timestamp).toLocaleString()}
                      </p>
                    </div>
                  </div>
                ))}
              </div>

              {/* Reply indicator */}
              {selectedConv.status === 'awaiting_reply' && (
                <div className="p-4 border-t border-border/40 bg-muted/20">
                  <div className="flex items-center gap-3">
                    <div className="h-2 w-2 rounded-full bg-yellow-500 animate-pulse" />
                    <span className="text-sm text-muted-foreground">Draft pending approval</span>
                    <div className="flex-1" />
                    <Button size="sm">View Draft</Button>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center">
                <Mail className="h-12 w-12 mx-auto text-muted-foreground/50 mb-4" />
                <p className="text-muted-foreground">Select a conversation to view</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
