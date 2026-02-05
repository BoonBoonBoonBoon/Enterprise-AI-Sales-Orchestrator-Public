'use client';

import { useEffect, useMemo, useState } from 'react';
import { Header } from '@/components/layout';
import {
  User,
  Mail,
  Key,
  Bell,
  Shield,
  Palette,
  Link2,
  Bot,
  ChevronRight,
  Check,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { createClient } from '@/lib/supabase/client';
import { getCurrentProfile } from '@/lib/profile';

const tabs = [
  { id: 'account', label: 'Account', icon: User },
  { id: 'voice', label: 'AI Voice', icon: Bot },
  { id: 'notifications', label: 'Notifications', icon: Bell },
  { id: 'integrations', label: 'Integrations', icon: Link2 },
  { id: 'security', label: 'Security', icon: Shield },
];

const toneOptions = [
  { id: 'professional', label: 'Professional', description: 'Formal and business-appropriate' },
  { id: 'friendly', label: 'Friendly', description: 'Warm and approachable' },
  { id: 'casual', label: 'Casual', description: 'Relaxed and conversational' },
  { id: 'direct', label: 'Direct', description: 'Concise and to-the-point' },
];

const integrations = [
  { id: 'gmail', name: 'Gmail', icon: Mail, connected: true, status: 'Connected' },
  { id: 'calendar', name: 'Google Calendar', icon: Mail, connected: true, status: 'Connected' },
  { id: 'slack', name: 'Slack', icon: Mail, connected: false, status: 'Not connected' },
  { id: 'hubspot', name: 'HubSpot', icon: Mail, connected: false, status: 'Not connected' },
];

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState('account');
  const [tone, setTone] = useState('friendly');
  const [autoMode, setAutoMode] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [profileNotice, setProfileNotice] = useState<string | null>(null);
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [company, setCompany] = useState('');
  const [phone, setPhone] = useState('');
  const [profileSnapshot, setProfileSnapshot] = useState<{
    userId?: string | null;
    clientId?: string | null;
    clientName?: string | null;
    email?: string | null;
    fullName?: string | null;
  } | null>(null);
  const [notifications, setNotifications] = useState({
    draftReady: true,
    emailSent: false,
    newLead: true,
    weeklyDigest: true,
  });

  const loadProfile = () => {
    const supabase = createClient();
    return getCurrentProfile(supabase)
      .then((profile) => {
        if (!profile) {
          setProfileError('Unable to load your profile. Please sign in again.');
          setProfileSnapshot(null);
          return;
        }
        setFullName(profile.fullName || '');
        setEmail(profile.email || '');
        setCompany(profile.clientName || '');
        setPhone(profile.phone || '');
        setProfileSnapshot({
          userId: profile.userId,
          clientId: profile.clientId,
          clientName: profile.clientName,
          email: profile.email,
          fullName: profile.fullName,
        });
      })
      .catch((err) => {
        setProfileError(err instanceof Error ? err.message : 'Unable to load profile');
      });
  };

  useEffect(() => {
    loadProfile();
  }, []);

  const nameParts = useMemo(() => {
    const trimmed = fullName.trim();
    if (!trimmed) return { first: '', last: '' };
    const parts = trimmed.split(' ');
    return {
      first: parts[0] || '',
      last: parts.slice(1).join(' '),
    };
  }, [fullName]);

  const handleSaveProfile = async () => {
    setIsSaving(true);
    setProfileError(null);
    setProfileNotice(null);

    try {
      const supabase = createClient();
      const { data: sessionData } = await supabase.auth.getSession();
      if (!sessionData.session) {
        throw new Error('Session expired. Please sign in again.');
      }

      const { data: userData, error: userError } = await supabase.auth.getUser();
      if (userError || !userData.user) {
        throw new Error('Unable to load user session.');
      }

      const updatePayload: { data: Record<string, string | null>; email?: string } = {
        data: { name: fullName.trim() || null, phone: phone.trim() || null },
      };

      if (email.trim() && email.trim() !== (userData.user.email || '')) {
        updatePayload.email = email.trim();
      }

      const { error: authError } = await supabase.auth.updateUser(updatePayload);
      if (authError) {
        throw new Error(`Auth update failed: ${authError.message}`);
      }

      const { error: profileError } = await supabase
        .from('user_profiles')
        .upsert(
          {
            user_id: userData.user.id,
            full_name: fullName.trim() || null,
            phone: phone.trim() || null,
            email: userData.user.email ?? null,
          },
          { onConflict: 'user_id' }
        );

      if (profileError) {
        throw new Error(`Profile update failed: ${profileError.message}`);
      }

      setProfileNotice('Profile updated.');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to update profile';
      setProfileError(message);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <Header title="Settings" description="Manage your account and preferences" />

      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar */}
        <div className="w-64 border-r border-border p-4">
          <nav className="space-y-1">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                  activeTab === tab.id
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:bg-secondary hover:text-foreground'
                )}
              >
                <tab.icon className="h-4 w-4" />
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        {/* Content */}
        <div className="flex-1 p-6 overflow-auto">
          {/* Account */}
          {activeTab === 'account' && (
            <div className="max-w-2xl space-y-6">
              <div>
                <h2 className="text-lg font-semibold mb-4">Profile Information</h2>
                {profileError && (
                  <div className="mb-4 rounded-lg border border-destructive/20 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                    {profileError}
                  </div>
                )}
                {profileNotice && (
                  <div className="mb-4 rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700">
                    {profileNotice}
                  </div>
                )}
                <div className="space-y-4">
                  <div className="flex items-center gap-4">
                    <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center text-primary text-xl font-bold">
                      {(fullName || email || '?')
                        .split(' ')
                        .map((part) => part[0])
                        .join('')
                        .toUpperCase()
                        .slice(0, 2)}
                    </div>
                    <div>
                      <button className="px-3 py-1.5 text-sm font-medium rounded-lg border border-input hover:bg-secondary transition-colors">
                        Change photo
                      </button>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium mb-1.5">First name</label>
                      <input
                        type="text"
                        value={nameParts.first}
                        onChange={(event) => {
                          const next = `${event.target.value} ${nameParts.last}`.trim();
                          setFullName(next);
                        }}
                        className="w-full px-3 py-2 rounded-lg border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium mb-1.5">Last name</label>
                      <input
                        type="text"
                        value={nameParts.last}
                        onChange={(event) => {
                          const next = `${nameParts.first} ${event.target.value}`.trim();
                          setFullName(next);
                        }}
                        className="w-full px-3 py-2 rounded-lg border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-1.5">Email</label>
                    <input
                      type="email"
                      value={email}
                      readOnly
                      className="w-full px-3 py-2 rounded-lg border border-input bg-muted/50 text-sm text-muted-foreground focus:outline-none"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-1.5">Company</label>
                    <input
                      type="text"
                      value={company}
                      readOnly
                      className="w-full px-3 py-2 rounded-lg border border-input bg-muted/50 text-sm text-muted-foreground focus:outline-none"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-1.5">Phone</label>
                    <input
                      type="tel"
                      value={phone}
                      onChange={(event) => setPhone(event.target.value)}
                      className="w-full px-3 py-2 rounded-lg border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                    />
                  </div>
                </div>
              </div>

              <div className="pt-4 border-t border-border">
                <button
                  onClick={handleSaveProfile}
                  disabled={isSaving}
                  className="px-4 py-2 rounded-lg bg-primary text-primary-foreground font-medium text-sm hover:bg-primary/90 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {isSaving ? 'Saving...' : 'Save changes'}
                </button>
              </div>

              <div className="pt-6 border-t border-border">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-semibold">Profile Diagnostics</h3>
                  <button
                    onClick={loadProfile}
                    className="px-3 py-1.5 text-xs font-medium rounded-lg border border-input hover:bg-secondary transition-colors"
                  >
                    Refresh
                  </button>
                </div>
                <div className="rounded-lg border border-border bg-muted/30 p-3 text-xs text-muted-foreground space-y-1">
                  <div>User ID: {profileSnapshot?.userId || '—'}</div>
                  <div>Client ID: {profileSnapshot?.clientId || '—'}</div>
                  <div>Client Name: {profileSnapshot?.clientName || '—'}</div>
                  <div>Email: {profileSnapshot?.email || '—'}</div>
                  <div>Full Name: {profileSnapshot?.fullName || '—'}</div>
                </div>
              </div>
            </div>
          )}

          {/* AI Voice */}
          {activeTab === 'voice' && (
            <div className="max-w-2xl space-y-6">
              <div>
                <h2 className="text-lg font-semibold mb-2">AI Voice & Tone</h2>
                <p className="text-sm text-muted-foreground mb-4">
                  Customize how Monty communicates on your behalf
                </p>

                <div className="grid grid-cols-2 gap-3">
                  {toneOptions.map((option) => (
                    <button
                      key={option.id}
                      onClick={() => setTone(option.id)}
                      className={cn(
                        'p-4 rounded-xl border text-left transition-all',
                        tone === option.id
                          ? 'border-primary bg-primary/5 ring-1 ring-primary'
                          : 'border-border hover:border-primary/50'
                      )}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-medium">{option.label}</span>
                        {tone === option.id && <Check className="h-4 w-4 text-primary" />}
                      </div>
                      <span className="text-sm text-muted-foreground">{option.description}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div className="pt-6 border-t border-border">
                <h2 className="text-lg font-semibold mb-2">Automation Mode</h2>
                <p className="text-sm text-muted-foreground mb-4">
                  Choose how much control Monty has over sending emails
                </p>

                <div className="space-y-3">
                  <button
                    onClick={() => setAutoMode(false)}
                    className={cn(
                      'w-full p-4 rounded-xl border text-left transition-all',
                      !autoMode
                        ? 'border-primary bg-primary/5 ring-1 ring-primary'
                        : 'border-border hover:border-primary/50'
                    )}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-medium">Review Mode</span>
                      {!autoMode && <Check className="h-4 w-4 text-primary" />}
                    </div>
                    <span className="text-sm text-muted-foreground">
                      Monty drafts responses for you to review and approve before sending
                    </span>
                  </button>

                  <button
                    onClick={() => setAutoMode(true)}
                    className={cn(
                      'w-full p-4 rounded-xl border text-left transition-all',
                      autoMode
                        ? 'border-primary bg-primary/5 ring-1 ring-primary'
                        : 'border-border hover:border-primary/50'
                    )}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-medium">Autopilot Mode</span>
                      {autoMode && <Check className="h-4 w-4 text-primary" />}
                    </div>
                    <span className="text-sm text-muted-foreground">
                      Monty sends responses automatically based on your rules and preferences
                    </span>
                  </button>
                </div>
              </div>

              <div className="pt-6 border-t border-border">
                <h2 className="text-lg font-semibold mb-2">Email Signature</h2>
                <p className="text-sm text-muted-foreground mb-4">
                  Your signature will be appended to all outgoing emails
                </p>

                <textarea
                  rows={4}
                  defaultValue={`Best regards,
John Doe
VP of Sales, Acme Corp
john@company.com | (555) 123-4567`}
                  className="w-full px-3 py-2 rounded-lg border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring font-mono"
                />
              </div>

              <div className="pt-4 border-t border-border">
                <button className="px-4 py-2 rounded-lg bg-primary text-primary-foreground font-medium text-sm hover:bg-primary/90 transition-colors">
                  Save preferences
                </button>
              </div>
            </div>
          )}

          {/* Notifications */}
          {activeTab === 'notifications' && (
            <div className="max-w-2xl space-y-6">
              <div>
                <h2 className="text-lg font-semibold mb-2">Email Notifications</h2>
                <p className="text-sm text-muted-foreground mb-4">
                  Choose what updates you want to receive
                </p>

                <div className="space-y-4">
                  {[
                    { key: 'draftReady', label: 'Draft ready for review', desc: 'Get notified when a new draft needs your approval' },
                    { key: 'emailSent', label: 'Email sent', desc: 'Confirmation when emails are sent on your behalf' },
                    { key: 'newLead', label: 'New lead qualified', desc: 'Alert when a new lead enters your pipeline' },
                    { key: 'weeklyDigest', label: 'Weekly digest', desc: 'Summary of your activity and performance' },
                  ].map((item) => (
                    <div
                      key={item.key}
                      className="flex items-center justify-between p-4 rounded-xl border border-border"
                    >
                      <div>
                        <div className="font-medium">{item.label}</div>
                        <div className="text-sm text-muted-foreground">{item.desc}</div>
                      </div>
                      <button
                        onClick={() =>
                          setNotifications((prev) => ({
                            ...prev,
                            [item.key]: !prev[item.key as keyof typeof prev],
                          }))
                        }
                        className={cn(
                          'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                          notifications[item.key as keyof typeof notifications]
                            ? 'bg-primary'
                            : 'bg-gray-200'
                        )}
                      >
                        <span
                          className={cn(
                            'inline-block h-4 w-4 transform rounded-full bg-white transition-transform',
                            notifications[item.key as keyof typeof notifications]
                              ? 'translate-x-6'
                              : 'translate-x-1'
                          )}
                        />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Integrations */}
          {activeTab === 'integrations' && (
            <div className="max-w-2xl space-y-6">
              <div>
                <h2 className="text-lg font-semibold mb-2">Connected Apps</h2>
                <p className="text-sm text-muted-foreground mb-4">
                  Manage your integrations and connected services
                </p>

                <div className="space-y-3">
                  {integrations.map((integration) => (
                    <div
                      key={integration.id}
                      className="flex items-center justify-between p-4 rounded-xl border border-border"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-lg bg-secondary flex items-center justify-center">
                          <integration.icon className="h-5 w-5" />
                        </div>
                        <div>
                          <div className="font-medium">{integration.name}</div>
                          <div
                            className={cn(
                              'text-sm',
                              integration.connected ? 'text-emerald-600' : 'text-muted-foreground'
                            )}
                          >
                            {integration.status}
                          </div>
                        </div>
                      </div>
                      <button
                        className={cn(
                          'px-3 py-1.5 text-sm font-medium rounded-lg transition-colors',
                          integration.connected
                            ? 'border border-input hover:bg-secondary'
                            : 'bg-primary text-primary-foreground hover:bg-primary/90'
                        )}
                      >
                        {integration.connected ? 'Disconnect' : 'Connect'}
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Security */}
          {activeTab === 'security' && (
            <div className="max-w-2xl space-y-6">
              <div>
                <h2 className="text-lg font-semibold mb-2">Password</h2>
                <p className="text-sm text-muted-foreground mb-4">
                  Update your password to keep your account secure
                </p>

                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium mb-1.5">Current password</label>
                    <input
                      type="password"
                      className="w-full px-3 py-2 rounded-lg border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1.5">New password</label>
                    <input
                      type="password"
                      className="w-full px-3 py-2 rounded-lg border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1.5">Confirm new password</label>
                    <input
                      type="password"
                      className="w-full px-3 py-2 rounded-lg border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                    />
                  </div>
                </div>

                <button className="mt-4 px-4 py-2 rounded-lg bg-primary text-primary-foreground font-medium text-sm hover:bg-primary/90 transition-colors">
                  Update password
                </button>
              </div>

              <div className="pt-6 border-t border-border">
                <h2 className="text-lg font-semibold mb-2">Two-Factor Authentication</h2>
                <p className="text-sm text-muted-foreground mb-4">
                  Add an extra layer of security to your account
                </p>

                <button className="px-4 py-2 rounded-lg border border-input font-medium text-sm hover:bg-secondary transition-colors">
                  Enable 2FA
                </button>
              </div>

              <div className="pt-6 border-t border-border">
                <h2 className="text-lg font-semibold mb-2 text-destructive">Danger Zone</h2>
                <p className="text-sm text-muted-foreground mb-4">
                  Permanently delete your account and all associated data
                </p>

                <button className="px-4 py-2 rounded-lg border border-destructive text-destructive font-medium text-sm hover:bg-destructive/10 transition-colors">
                  Delete account
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
