'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { createClient } from '@/lib/supabase/client';

export default function ResetPasswordPage() {
  const router = useRouter();
  const supabase = useMemo(() => createClient(), []);

  const [hasSession, setHasSession] = useState<boolean | null>(null);
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setHasSession(!!data.session);
    });
  }, [supabase]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (password.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setIsLoading(true);

    try {
      const { error: updateError } = await supabase.auth.updateUser({ password });
      if (updateError) throw updateError;

      setDone(true);
      await supabase.auth.signOut();
      router.push('/login');
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to update password');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-8">
      <div className="w-full max-w-md">
        <div className="mb-6">
          <h1 className="text-2xl font-bold">Choose a new password</h1>
          <p className="text-muted-foreground mt-2">
            Set a password for your account.
          </p>
        </div>

        {error && (
          <div className="mb-6 p-4 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm">
            {error}
          </div>
        )}

        {hasSession === false && (
          <div className="mb-6 p-4 rounded-lg border border-border bg-secondary/30 text-sm">
            This page must be opened from the password reset email link. If you already clicked it, try requesting a new reset link.
            <div className="mt-3">
              <Link className="text-primary hover:underline" href="/forgot-password">
                Request a new reset link
              </Link>
            </div>
          </div>
        )}

        {done ? (
          <div className="space-y-6">
            <div className="p-4 rounded-lg border border-border bg-secondary/30 text-sm">
              Password updated. You can now sign in.
            </div>
            <Link className="text-primary hover:underline" href="/login">
              Go to sign in
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label htmlFor="password" className="block text-sm font-medium mb-2">
                New password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                className="w-full px-4 py-2.5 rounded-lg border border-input bg-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1"
              />
            </div>

            <div>
              <label htmlFor="confirmPassword" className="block text-sm font-medium mb-2">
                Confirm password
              </label>
              <input
                id="confirmPassword"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="••••••••"
                required
                className="w-full px-4 py-2.5 rounded-lg border border-input bg-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1"
              />
            </div>

            <button
              type="submit"
              disabled={isLoading || hasSession === false}
              className="w-full py-2.5 rounded-lg bg-primary text-primary-foreground font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
            >
              {isLoading ? 'Updating…' : 'Update password'}
            </button>

            <div className="text-sm">
              <Link className="text-primary hover:underline" href="/login">
                Back to sign in
              </Link>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
