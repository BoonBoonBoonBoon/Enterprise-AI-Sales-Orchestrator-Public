'use client';

import { useState } from 'react';
import Link from 'next/link';
import { createClient } from '@/lib/supabase/client';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      const supabase = createClient();
      const { error: resetError } = await supabase.auth.resetPasswordForEmail(email, {
        redirectTo: `${window.location.origin}/auth/callback?next=/reset-password`,
      });

      if (resetError) throw resetError;
      setSent(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to send reset email');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-8">
      <div className="w-full max-w-md">
        <div className="mb-6">
          <h1 className="text-2xl font-bold">Reset your password</h1>
          <p className="text-muted-foreground mt-2">
            Enter your email and we’ll send you a reset link.
          </p>
        </div>

        {error && (
          <div className="mb-6 p-4 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm">
            {error}
          </div>
        )}

        {sent ? (
          <div className="space-y-6">
            <div className="p-4 rounded-lg border border-border bg-secondary/30 text-sm">
              If an account exists for <span className="font-medium">{email}</span>, you’ll receive a password reset email shortly.
            </div>
            <Link className="text-primary hover:underline" href="/login">
              Back to sign in
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label htmlFor="email" className="block text-sm font-medium mb-2">
                Email
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                required
                className="w-full px-4 py-2.5 rounded-lg border border-input bg-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1"
              />
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-2.5 rounded-lg bg-primary text-primary-foreground font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
            >
              {isLoading ? 'Sending…' : 'Send reset link'}
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
