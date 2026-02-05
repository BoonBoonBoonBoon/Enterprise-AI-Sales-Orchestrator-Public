'use client';

import { useState, type FormEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { createClient } from '@/lib/supabase/client';
import { Mail, Lock, User, ArrowRight, Loader2, Sparkles, CheckCircle } from 'lucide-react';

export default function SignUpPage() {
  const router = useRouter();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      const supabase = createClient();
      const { error: signUpError } = await supabase.auth.signUp({
        email,
        password,
        options: {
          data: { name },
          emailRedirectTo: `${window.location.origin}/auth/callback`,
        },
      });

      if (signUpError) {
        throw signUpError;
      }

      setSuccess(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to create account');
    } finally {
      setIsLoading(false);
    }
  };

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center p-8">
        <div className="max-w-md text-center">
          <div className="h-16 w-16 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-6">
            <CheckCircle className="h-8 w-8 text-primary" />
          </div>
          <h1 className="text-2xl font-bold mb-3">Check your email</h1>
          <p className="text-muted-foreground mb-6">
            We sent a confirmation link to <span className="font-medium text-foreground">{email}</span>.
            Click the link to activate your account.
          </p>
          <Link
            href="/login"
            className="inline-flex items-center gap-2 text-primary hover:underline font-medium"
          >
            Back to sign in
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex">
      {/* Left panel - Branding */}
      <div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 relative overflow-hidden">
        <div className="absolute inset-0 opacity-30">
          <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-emerald-500/20 rounded-full blur-3xl" />
          <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-blue-500/20 rounded-full blur-3xl" />
        </div>

        <div className="relative z-10 flex flex-col justify-center p-12 max-w-lg">
          <div className="flex items-center gap-3 mb-8">
            <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center">
              <Sparkles className="h-7 w-7 text-white" />
            </div>
            <span className="font-bold text-3xl text-white">Monty</span>
          </div>

          <h1 className="text-4xl font-bold text-white mb-4">
            Start automating your outreach
          </h1>
          <p className="text-lg text-slate-300 leading-relaxed">
            Join teams using Monty to draft personalized emails, qualify leads automatically, and close more deals.
          </p>

          <div className="mt-12 space-y-4">
            {[
              'AI drafts replies in your voice',
              'Review before anything sends',
              'Automatic lead qualification',
              'Meeting booking on autopilot',
            ].map((feature) => (
              <div key={feature} className="flex items-center gap-3">
                <CheckCircle className="h-5 w-5 text-emerald-400" />
                <span className="text-slate-300">{feature}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right panel - Form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          {/* Mobile logo */}
          <div className="lg:hidden flex items-center gap-3 mb-8">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center">
              <Sparkles className="h-5 w-5 text-white" />
            </div>
            <span className="font-bold text-2xl">Monty</span>
          </div>

          <div className="mb-8">
            <h2 className="text-2xl font-bold">Create your account</h2>
            <p className="text-muted-foreground mt-2">
              Already have an account?{' '}
              <Link href="/login" className="text-primary hover:underline font-medium">
                Sign in
              </Link>
            </p>
          </div>

          {error && (
            <div className="mb-6 p-4 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label htmlFor="name" className="block text-sm font-medium mb-2">
                Full name
              </label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <input
                  id="name"
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Jane Smith"
                  required
                  className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-input bg-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1"
                />
              </div>
            </div>

            <div>
              <label htmlFor="email" className="block text-sm font-medium mb-2">
                Work email
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@company.com"
                  required
                  className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-input bg-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1"
                />
              </div>
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium mb-2">
                Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  minLength={8}
                  className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-input bg-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1"
                />
              </div>
              <p className="text-xs text-muted-foreground mt-1.5">At least 8 characters</p>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-2.5 rounded-lg bg-primary text-primary-foreground font-medium hover:bg-primary/90 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <>
                  Create account
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>
          </form>

          <p className="mt-8 text-center text-xs text-muted-foreground">
            By signing up, you agree to our{' '}
            <Link href="/terms" className="underline hover:text-foreground">Terms</Link>
            {' '}and{' '}
            <Link href="/privacy" className="underline hover:text-foreground">Privacy Policy</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
