'use client';

import { Header } from '@/components/layout/header';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  User,
  Building2,
  Shield,
  Bell,
  Zap,
  CreditCard,
  Users,
  ToggleLeft,
  ToggleRight,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';
import { supabase } from '@/lib/supabase';

export default function SettingsPage() {
  const [approvalMode, setApprovalMode] = useState(true);
  const [autoSendEnabled, setAutoSendEnabled] = useState(false);
  const [profileName, setProfileName] = useState('');
  const [profileEmail, setProfileEmail] = useState('');
  const [isSavingProfile, setIsSavingProfile] = useState(false);
  const [profileMessage, setProfileMessage] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    const hydrateProfile = async () => {
      const { data, error } = await supabase.auth.getUser();
      if (!isMounted || error || !data.user) {
        return;
      }
      const meta = data.user.user_metadata || {};
      const name = meta.name || meta.full_name || meta.display_name || '';
      setProfileName(name || data.user.email || '');
      setProfileEmail(data.user.email || '');
    };

    hydrateProfile();

    const { data: authListener } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!isMounted) {
        return;
      }
      const user = session?.user;
      const meta = user?.user_metadata || {};
      const name = meta.name || meta.full_name || meta.display_name || '';
      setProfileName(name || user?.email || '');
      setProfileEmail(user?.email || '');
    });

    return () => {
      isMounted = false;
      authListener?.subscription?.unsubscribe();
    };
  }, []);

  const handleSaveProfile = async () => {
    setIsSavingProfile(true);
    setProfileMessage(null);
    const trimmedName = profileName.trim();

    const { error } = await supabase.auth.updateUser({
      data: {
        name: trimmedName,
        full_name: trimmedName,
        display_name: trimmedName,
      },
    });

    if (error) {
      setProfileMessage(error.message);
    } else {
      setProfileMessage('Profile updated');
    }

    setIsSavingProfile(false);
  };

  return (
    <div className="flex flex-col h-full">
      <Header title="Settings" description="Manage your account and preferences" />

      <div className="flex-1 p-6 overflow-auto">
        <div className="max-w-3xl mx-auto space-y-6">
          {/* Profile */}
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <User className="h-5 w-5 text-muted-foreground" />
                <CardTitle className="text-lg">Profile</CardTitle>
              </div>
              <CardDescription>Your personal information</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="name">Full Name</Label>
                  <Input
                    id="name"
                    value={profileName}
                    onChange={(event) => setProfileName(event.target.value)}
                    placeholder="Your name"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="email">Email</Label>
                  <Input id="email" value={profileEmail} disabled />
                </div>
              </div>
              {profileMessage && (
                <p className="text-sm text-muted-foreground">{profileMessage}</p>
              )}
              <Button onClick={handleSaveProfile} disabled={isSavingProfile}>
                {isSavingProfile ? 'Saving…' : 'Save Changes'}
              </Button>
            </CardContent>
          </Card>

          {/* Organization */}
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Building2 className="h-5 w-5 text-muted-foreground" />
                <CardTitle className="text-lg">Organization</CardTitle>
              </div>
              <CardDescription>Your company details</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="company">Company Name</Label>
                  <Input id="company" defaultValue="Acme Inc." />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="website">Website</Label>
                  <Input id="website" defaultValue="https://acme.com" />
                </div>
              </div>
              <Button>Save Changes</Button>
            </CardContent>
          </Card>

          {/* Sending Policy */}
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Shield className="h-5 w-5 text-muted-foreground" />
                <CardTitle className="text-lg">Sending Policy</CardTitle>
              </div>
              <CardDescription>Control how emails are sent</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Approval Mode */}
              <div className="flex items-center justify-between p-4 rounded-lg border border-border/60 bg-muted/20">
                <div className="flex items-start gap-3">
                  <div className="p-2 rounded-lg bg-green-500/10 text-green-500">
                    <Shield className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="font-medium">Approval Required</p>
                    <p className="text-sm text-muted-foreground mt-0.5">
                      All drafts require manual approval before sending
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setApprovalMode(!approvalMode)}
                  className="text-primary"
                >
                  {approvalMode ? (
                    <ToggleRight className="h-8 w-8" />
                  ) : (
                    <ToggleLeft className="h-8 w-8 text-muted-foreground" />
                  )}
                </button>
              </div>

              {/* Auto-send */}
              <div
                className={cn(
                  'flex items-center justify-between p-4 rounded-lg border border-border/60',
                  !approvalMode ? 'bg-muted/20' : 'bg-muted/10 opacity-50'
                )}
              >
                <div className="flex items-start gap-3">
                  <div className="p-2 rounded-lg bg-yellow-500/10 text-yellow-500">
                    <Zap className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="font-medium">Auto-Send (Controlled)</p>
                    <p className="text-sm text-muted-foreground mt-0.5">
                      Automatically send approved-pattern replies
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => !approvalMode && setAutoSendEnabled(!autoSendEnabled)}
                  disabled={approvalMode}
                  className={cn(approvalMode && 'cursor-not-allowed')}
                >
                  {autoSendEnabled && !approvalMode ? (
                    <ToggleRight className="h-8 w-8 text-primary" />
                  ) : (
                    <ToggleLeft className="h-8 w-8 text-muted-foreground" />
                  )}
                </button>
              </div>

              {/* Throttles */}
              <div className="p-4 rounded-lg border border-border/60 bg-muted/20">
                <p className="font-medium mb-4">Sending Limits</p>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="hourly">Max emails per hour</Label>
                    <Input id="hourly" type="number" defaultValue="20" />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="daily">Max new threads per day</Label>
                    <Input id="daily" type="number" defaultValue="50" />
                  </div>
                </div>
              </div>

              <Button>Save Policy</Button>
            </CardContent>
          </Card>

          {/* Team */}
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Users className="h-5 w-5 text-muted-foreground" />
                <CardTitle className="text-lg">Team</CardTitle>
              </div>
              <CardDescription>Manage team members and roles</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {[
                  { name: 'John Doe', email: 'john@company.com', role: 'Admin' },
                  { name: 'Jane Smith', email: 'jane@company.com', role: 'Operator' },
                  { name: 'Bob Wilson', email: 'bob@company.com', role: 'Viewer' },
                ].map((member, i) => (
                  <div key={i} className="flex items-center justify-between p-3 rounded-lg border border-border/40">
                    <div className="flex items-center gap-3">
                      <div className="h-8 w-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-white text-xs font-medium">
                        {member.name
                          .split(' ')
                          .map((n) => n[0])
                          .join('')}
                      </div>
                      <div>
                        <p className="text-sm font-medium">{member.name}</p>
                        <p className="text-xs text-muted-foreground">{member.email}</p>
                      </div>
                    </div>
                    <span className="text-xs px-2 py-1 rounded bg-muted">{member.role}</span>
                  </div>
                ))}
                <Button variant="outline" className="w-full">
                  Invite Team Member
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Billing */}
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <CreditCard className="h-5 w-5 text-muted-foreground" />
                <CardTitle className="text-lg">Billing</CardTitle>
              </div>
              <CardDescription>Manage your subscription and invoices</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="p-4 rounded-lg border border-primary/30 bg-primary/5 mb-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-semibold">Pro Plan</p>
                    <p className="text-sm text-muted-foreground">$99/month · 1,000 emails/month</p>
                  </div>
                  <Button variant="outline" size="sm">
                    Manage
                  </Button>
                </div>
                <div className="mt-4">
                  <div className="flex items-center justify-between text-sm mb-1">
                    <span>Usage this month</span>
                    <span>487 / 1,000</span>
                  </div>
                  <div className="h-2 rounded-full bg-muted overflow-hidden">
                    <div className="h-full w-[48.7%] rounded-full bg-primary" />
                  </div>
                </div>
              </div>
              <Button variant="outline" className="w-full">
                View Invoices
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
