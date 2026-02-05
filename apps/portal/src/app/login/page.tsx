'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Zap, Mail, ArrowRight, Github } from 'lucide-react';
import { supabase } from '@/lib/supabase';

export default function LoginPage() {
  const [isLoading, setIsLoading] = useState(false);
  const [isSignUp, setIsSignUp] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      if (data.session) {
        window.location.href = '/dashboard';
      }
    });
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      if (isSignUp) {
        const { error: signUpError } = await supabase.auth.signUp({
          email,
          password,
          options: {
            data: { name },
          },
        });

        if (signUpError) {
          throw signUpError;
        }
      } else {
        const { error: signInError } = await supabase.auth.signInWithPassword({
          email,
          password,
        });

        if (signInError) {
          throw signInError;
        }
      }

      window.location.href = '/dashboard';
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to authenticate');
    } finally {
      setIsLoading(false);
    }
  };

  const handleOAuth = async (provider: 'google' | 'github') => {
    setIsLoading(true);
    setError(null);
    const { error: oauthError } = await supabase.auth.signInWithOAuth({
      provider,
      options: {
        redirectTo: `${window.location.origin}/dashboard`,
      },
    });

    if (oauthError) {
      setError(oauthError.message);
      setIsLoading(false);
    }
  };


  return (
    <div className="min-h-screen flex">
      {/* Left panel - Branding */}
      <div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 relative overflow-hidden">
        {/* Background effects */}
        <div className="absolute inset-0 bg-grid opacity-30" />
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-purple-500/10 rounded-full blur-3xl" />

        <div className="relative z-10 flex flex-col justify-center p-12">
          <div className="flex items-center gap-3 mb-8">
            <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
              <Zap className="h-7 w-7 text-white" />
            </div>
            <span className="font-bold text-3xl text-white">Agentic</span>
          </div>

          <h1 className="text-4xl font-bold text-white mb-4">
            AI-Powered Email
            <br />
            <span className="gradient-text">Automation</span>
          </h1>

          <p className="text-lg text-slate-400 mb-8 max-w-md">
            Automate your B2B outreach with intelligent replies, approval workflows, and complete visibility.
          </p>

          <div className="space-y-4">
            <div className="flex items-center gap-3 text-slate-300">
              <div className="h-8 w-8 rounded-lg bg-blue-500/20 flex items-center justify-center">
                <Mail className="h-4 w-4 text-blue-400" />
              </div>
              <span>Smart draft generation with context</span>
            </div>
            <div className="flex items-center gap-3 text-slate-300">
              <div className="h-8 w-8 rounded-lg bg-purple-500/20 flex items-center justify-center">
                <Zap className="h-4 w-4 text-purple-400" />
              </div>
              <span>Human-in-the-loop approval workflows</span>
            </div>
            <div className="flex items-center gap-3 text-slate-300">
              <div className="h-8 w-8 rounded-lg bg-cyan-500/20 flex items-center justify-center">
                <ArrowRight className="h-4 w-4 text-cyan-400" />
              </div>
              <span>Full conversation and lead visibility</span>
            </div>
          </div>
        </div>
      </div>

      {/* Right panel - Auth form */}
      <div className="flex-1 flex items-center justify-center p-8 bg-background">
        <div className="w-full max-w-md">
          {/* Mobile logo */}
          <div className="lg:hidden flex items-center gap-2 justify-center mb-8">
            <div className="h-10 w-10 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
              <Zap className="h-6 w-6 text-white" />
            </div>
            <span className="font-bold text-2xl">Agentic</span>
          </div>

          <Card className="border-border/60">
            <CardHeader className="text-center">
              <CardTitle className="text-2xl">{isSignUp ? 'Create an account' : 'Welcome back'}</CardTitle>
              <CardDescription>
                {isSignUp
                  ? 'Enter your details to get started'
                  : 'Enter your credentials to access your portal'}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4">
                {isSignUp && (
                  <div className="space-y-2">
                    <Label htmlFor="name">Full Name</Label>
                    <Input
                      id="name"
                      placeholder="John Doe"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      required
                    />
                  </div>
                )}
                <div className="space-y-2">
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    type="email"
                    placeholder="john@company.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label htmlFor="password">Password</Label>
                    {!isSignUp && (
                      <Link href="/forgot-password" className="text-xs text-primary hover:underline">
                        Forgot password?
                      </Link>
                    )}
                  </div>
                  <Input
                    id="password"
                    type="password"
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />
                </div>

                {error && <div className="text-sm text-destructive">{error}</div>}

                <Button type="submit" className="w-full" disabled={isLoading}>
                  {isLoading ? (
                    <div className="h-5 w-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  ) : isSignUp ? (
                    'Create Account'
                  ) : (
                    'Sign In'
                  )}
                </Button>
              </form>

              <div className="relative my-6">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-border" />
                </div>
                <div className="relative flex justify-center text-xs uppercase">
                  <span className="bg-card px-2 text-muted-foreground">Or continue with</span>
                </div>
              </div>

              <div className="grid gap-3">
                <Button
                  variant="outline"
                  className="w-full gap-2"
                  type="button"
                  disabled={isLoading}
                  onClick={() => handleOAuth('google')}
                >
                  <svg className="h-4 w-4" viewBox="0 0 24 24">
                    <path
                      fill="currentColor"
                      d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                    />
                    <path
                      fill="currentColor"
                      d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                    />
                    <path
                      fill="currentColor"
                      d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                    />
                    <path
                      fill="currentColor"
                      d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                    />
                  </svg>
                  Google
                </Button>
                <Button
                  variant="outline"
                  className="w-full gap-2"
                  type="button"
                  disabled={isLoading}
                  onClick={() => handleOAuth('github')}
                >
                  <Github className="h-4 w-4" />
                  GitHub
                </Button>

              </div>

              <p className="text-center text-sm text-muted-foreground mt-6">
                {isSignUp ? 'Already have an account?' : "Don't have an account?"}{' '}
                <button
                  type="button"
                  onClick={() => setIsSignUp(!isSignUp)}
                  className="text-primary hover:underline font-medium"
                >
                  {isSignUp ? 'Sign in' : 'Sign up'}
                </button>
              </p>
            </CardContent>
          </Card>

          <p className="text-center text-xs text-muted-foreground mt-6">
            By continuing, you agree to our{' '}
            <Link href="/terms" className="underline hover:text-foreground">
              Terms of Service
            </Link>{' '}
            and{' '}
            <Link href="/privacy" className="underline hover:text-foreground">
              Privacy Policy
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
