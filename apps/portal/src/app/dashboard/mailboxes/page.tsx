'use client';

import { useEffect, useState } from 'react';
import { Header } from '@/components/layout/header';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Mail,
  Plus,
  CheckCircle,
  AlertCircle,
  RefreshCw,
  Trash2,
  Settings,
  MoreHorizontal,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { fetchWithAuth } from '@/lib/api';

type Mailbox = {
  id: string;
  email: string;
  provider: 'gmail' | 'outlook' | 'imap';
  status: 'connected' | 'disconnected' | 'error';
  last_sync?: string | null;
  messages_received: number;
  messages_sent: number;
  error?: string | null;
};

type MailboxListResponse = {
  mailboxes: Mailbox[];
  total: number;
};

export default function MailboxesPage() {
  const [mailboxes, setMailboxes] = useState<Mailbox[]>([]);
  const [showAddModal, setShowAddModal] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadMailboxes = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetchWithAuth('/api/v1/mailboxes');
      if (!res.ok) {
        throw new Error('Failed to load mailboxes');
      }
      const data = (await res.json()) as MailboxListResponse;
      setMailboxes(data.mailboxes ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load mailboxes');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMailboxes();
  }, []);

  return (
    <div className="flex flex-col h-full">
      <Header
        title="Mailboxes"
        description="Connect and manage your email accounts"
        action={{ label: 'Add Mailbox', onClick: () => setShowAddModal(true) }}
      />

      <div className="flex-1 p-6 overflow-auto">
        <div className="max-w-4xl mx-auto space-y-6">
          {/* Connected mailboxes */}
          <div className="space-y-4">
            {loading && <div className="p-4 text-sm text-muted-foreground">Loading mailboxes…</div>}
            {error && <div className="p-4 text-sm text-destructive">{error}</div>}
            {!loading && !error && mailboxes.map((mailbox) => (
              <Card
                key={mailbox.id}
                className={cn(
                  'overflow-hidden',
                  mailbox.status === 'error' && 'border-destructive/50'
                )}
              >
                <CardContent className="p-6">
                  <div className="flex items-start gap-4">
                    {/* Icon */}
                    <div
                      className={cn(
                        'h-12 w-12 rounded-lg flex items-center justify-center',
                        mailbox.provider === 'gmail'
                          ? 'bg-red-500/10 text-red-500'
                          : 'bg-blue-500/10 text-blue-500'
                      )}
                    >
                      <Mail className="h-6 w-6" />
                    </div>

                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <h3 className="font-semibold">{mailbox.email}</h3>
                        {mailbox.status === 'connected' && (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-green-500/10 text-green-500">
                            <CheckCircle className="h-3 w-3" />
                            Connected
                          </span>
                        )}
                        {mailbox.status === 'error' && (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-red-500/10 text-red-500">
                            <AlertCircle className="h-3 w-3" />
                            Error
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground mt-1 capitalize">
                        {mailbox.provider} · Last synced{' '}
                        {mailbox.last_sync ? new Date(mailbox.last_sync).toLocaleTimeString() : 'Never'}
                      </p>
                      {mailbox.error && (
                        <p className="text-sm text-destructive mt-2">{mailbox.error}</p>
                      )}

                      {/* Stats */}
                      <div className="flex items-center gap-6 mt-4">
                        <div>
                          <p className="text-2xl font-bold">{mailbox.messages_received}</p>
                          <p className="text-xs text-muted-foreground">Received</p>
                        </div>
                        <div>
                          <p className="text-2xl font-bold">{mailbox.messages_sent}</p>
                          <p className="text-xs text-muted-foreground">Sent</p>
                        </div>
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-2">
                      {mailbox.status === 'error' && (
                        <Button variant="outline" size="sm" className="gap-2">
                          <RefreshCw className="h-4 w-4" />
                          Reconnect
                        </Button>
                      )}
                      <Button variant="ghost" size="icon">
                        <Settings className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="icon" className="text-destructive hover:text-destructive">
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Add mailbox card */}
          <Card className="border-dashed">
            <CardContent className="p-6">
              <button
                onClick={() => setShowAddModal(true)}
                className="w-full flex flex-col items-center justify-center py-8 text-muted-foreground hover:text-foreground transition-colors"
              >
                <div className="h-12 w-12 rounded-lg border-2 border-dashed border-muted-foreground/30 flex items-center justify-center mb-4">
                  <Plus className="h-6 w-6" />
                </div>
                <p className="font-medium">Connect a new mailbox</p>
                <p className="text-sm mt-1">Support for Gmail, Outlook, and IMAP</p>
              </button>
            </CardContent>
          </Card>

          {/* Provider info */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Supported Providers</CardTitle>
              <CardDescription>Connect any of these email providers to get started</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-3">
              <div className="flex items-center gap-3 p-4 rounded-lg border border-border/60">
                <div className="h-10 w-10 rounded-lg bg-red-500/10 flex items-center justify-center">
                  <Mail className="h-5 w-5 text-red-500" />
                </div>
                <div>
                  <p className="font-medium">Gmail</p>
                  <p className="text-xs text-muted-foreground">OAuth 2.0</p>
                </div>
              </div>
              <div className="flex items-center gap-3 p-4 rounded-lg border border-border/60">
                <div className="h-10 w-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
                  <Mail className="h-5 w-5 text-blue-500" />
                </div>
                <div>
                  <p className="font-medium">Outlook</p>
                  <p className="text-xs text-muted-foreground">OAuth 2.0</p>
                </div>
              </div>
              <div className="flex items-center gap-3 p-4 rounded-lg border border-border/60">
                <div className="h-10 w-10 rounded-lg bg-gray-500/10 flex items-center justify-center">
                  <Mail className="h-5 w-5 text-gray-500" />
                </div>
                <div>
                  <p className="font-medium">IMAP</p>
                  <p className="text-xs text-muted-foreground">Custom server</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
