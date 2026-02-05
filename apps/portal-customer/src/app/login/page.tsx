'use client';

import { useState, useEffect, useRef, type FormEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { createClient } from '@/lib/supabase/client';
import {
  Lock,
  ArrowRight,
  Loader2,
  Sparkles,
  ChevronLeft,
  Zap,
  Mail,
  MessageSquare,
  BarChart3,
  Target,
} from 'lucide-react';

// Floating particle component
function FloatingParticle({ 
  delay, 
  duration, 
  size,
  color, 
  left, 
  top 
}: { 
  delay: number; 
  duration: number; 
  size: number; 
  color: string; 
  left: string; 
  top: string; 
}) {
  return (
    <div
      className="absolute rounded-full opacity-60 pointer-events-none"
      style={{
        width: size,
        height: size,
        left,
        top,
        background: color,
        filter: 'blur(1px)',
        animation: `float ${duration}s ease-in-out infinite`,
        animationDelay: `${delay}s`,
      }}
    />
  );
}

// Interactive feature card
function FeatureCard({ 
  icon: Icon, 
  title, 
  description, 
  color, 
  delay 
}: { 
  icon: typeof Mail; 
  title: string; 
  description: string; 
  color: string; 
  delay: number; 
}) {
  const [isHovered, setIsHovered] = useState(false);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setIsVisible(true), delay);
    return () => clearTimeout(timer);
  }, [delay]);
  
  return (
    <div
      className={`group relative p-4 rounded-xl backdrop-blur-md border border-white/10 bg-white/5 
                 hover:bg-white/10 hover:border-white/20 transition-all duration-300 cursor-pointer
                 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-5'}`}
      style={{ transitionDelay: `${delay}ms` }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div className="flex items-start gap-4">
        <div 
          className={`h-10 w-10 rounded-lg flex items-center justify-center shrink-0 transition-transform duration-300 ${isHovered ? 'scale-110' : ''}`}
          style={{ background: `${color}20` }}
        >
          <Icon className="h-5 w-5 transition-all duration-300" style={{ color }} />
        </div>
        <div>
          <p className="font-medium text-white group-hover:text-emerald-300 transition-colors">{title}</p>
          <p className="text-sm text-slate-400 group-hover:text-slate-300 transition-colors">{description}</p>
        </div>
      </div>
      {/* Hover glow effect */}
      <div 
        className="absolute inset-0 rounded-xl opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none"
        style={{ 
          background: `radial-gradient(circle at center, ${color}10 0%, transparent 70%)`,
        }}
      />
    </div>
  );
}

export default function LoginPage() {
  const router = useRouter();
  const marketingUrl = process.env.NEXT_PUBLIC_MARKETING_URL || 'http://localhost:3004';
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });
  const [isLogoHovered, setIsLogoHovered] = useState(false);
  const [mounted, setMounted] = useState(false);
  const leftPanelRef = useRef<HTMLDivElement>(null);

  // Mount animation
  useEffect(() => {
    setMounted(true);
  }, []);

  // Track mouse for parallax effect
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (leftPanelRef.current) {
        const rect = leftPanelRef.current.getBoundingClientRect();
        setMousePosition({
          x: (e.clientX - rect.left) / rect.width - 0.5,
          y: (e.clientY - rect.top) / rect.height - 0.5,
        });
      }
    };

    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      const supabase = createClient();
      const { error: signInError } = await supabase.auth.signInWithPassword({
        email,
        password,
      });

      if (signInError) {
        if (signInError.message?.toLowerCase().includes('invalid login credentials')) {
          throw new Error(
            'Invalid email or password. If you originally signed up with Google, use "Continue with Google". Otherwise, reset your password.'
          );
        }
        throw signInError;
      }

      router.push('/dashboard');
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to sign in');
    } finally {
      setIsLoading(false);
    }
  };

  const handleOAuth = async (provider: 'google') => {
    setIsLoading(true);
    setError(null);

    const supabase = createClient();
    const { error: oauthError } = await supabase.auth.signInWithOAuth({
      provider,
      options: {
        redirectTo: `${window.location.origin}/auth/callback`,
      },
    });

    if (oauthError) {
      setError(oauthError.message);
      setIsLoading(false);
    }
  };

  const features = [
    { icon: Mail, title: 'Smart Drafts', description: 'AI writes, you approve', color: '#10b981' },
    { icon: BarChart3, title: 'Live Analytics', description: 'Track every interaction', color: '#3b82f6' },
    { icon: Target, title: 'Lead Scoring', description: 'Focus on what matters', color: '#8b5cf6' },
    { icon: MessageSquare, title: 'Auto Replies', description: 'Never miss a beat', color: '#f59e0b' },
  ];

  const particles = [
    { delay: 0, duration: 8, size: 6, color: '#10b981', left: '10%', top: '20%' },
    { delay: 1, duration: 10, size: 4, color: '#3b82f6', left: '80%', top: '10%' },
    { delay: 2, duration: 12, size: 8, color: '#8b5cf6', left: '70%', top: '60%' },
    { delay: 0.5, duration: 9, size: 5, color: '#10b981', left: '20%', top: '70%' },
    { delay: 1.5, duration: 11, size: 3, color: '#f59e0b', left: '60%', top: '30%' },
    { delay: 2.5, duration: 7, size: 7, color: '#3b82f6', left: '30%', top: '50%' },
    { delay: 3, duration: 13, size: 4, color: '#10b981', left: '85%', top: '80%' },
    { delay: 0.8, duration: 8, size: 6, color: '#8b5cf6', left: '15%', top: '40%' },
  ];

  return (
    <>
      <style jsx global>{`
        @keyframes float {
          0%, 100% { transform: translateY(0) translateX(0); opacity: 0.6; }
          25% { transform: translateY(-20px) translateX(10px); opacity: 0.8; }
          50% { transform: translateY(-10px) translateX(-5px); opacity: 0.4; }
          75% { transform: translateY(-30px) translateX(5px); opacity: 0.7; }
        }
        @keyframes ping-slow {
          0% { transform: scale(1); opacity: 0.5; }
          75%, 100% { transform: scale(1.5); opacity: 0; }
        }
        @keyframes orbit {
          from { transform: rotate(0deg) translateX(30px) rotate(0deg); }
          to { transform: rotate(360deg) translateX(30px) rotate(-360deg); }
        }
        @keyframes pulse-glow {
          0%, 100% { opacity: 0.5; }
          50% { opacity: 1; }
        }
      `}</style>

      <div className="min-h-screen flex">
        {/* Left panel - Interactive Branding */}
        <div 
          ref={leftPanelRef}
          className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 relative overflow-hidden"
        >
          {/* Animated gradient orbs that follow mouse */}
          <div 
            className="absolute w-[600px] h-[600px] bg-emerald-500/20 rounded-full blur-[120px] transition-transform duration-1000 ease-out"
            style={{
              left: '20%',
              top: '20%',
              transform: `translate(${mousePosition.x * 50}px, ${mousePosition.y * 50}px)`,
            }}
          />
          <div 
            className="absolute w-[500px] h-[500px] bg-blue-500/15 rounded-full blur-[100px] transition-transform duration-1000 ease-out"
            style={{
              right: '10%',
              bottom: '20%',
              transform: `translate(${mousePosition.x * -30}px, ${mousePosition.y * -30}px)`,
            }}
          />
          <div 
            className="absolute w-[300px] h-[300px] bg-purple-500/10 rounded-full blur-[80px] transition-transform duration-1000 ease-out"
            style={{
              left: '50%',
              top: '60%',
              transform: `translate(${mousePosition.x * 40}px, ${mousePosition.y * 40}px)`,
            }}
          />

          {/* Floating particles */}
          {particles.map((p, i) => (
            <FloatingParticle key={i} {...p} />
          ))}

          {/* Grid pattern overlay */}
          <div 
            className="absolute inset-0 opacity-[0.03]"
            style={{
              backgroundImage: `linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px),
                               linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)`,
              backgroundSize: '50px 50px',
            }}
          />

          <div className="relative z-10 mx-auto flex w-full max-w-md flex-col justify-center p-8">
            {/* Back button */}
            <div className={`mb-8 transition-all duration-500 ${mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}`}>
              <button
                type="button"
                onClick={() => {
                  if (marketingUrl.startsWith('/')) {
                    router.push(marketingUrl);
                    return;
                  }

                  window.location.assign(marketingUrl);
                }}
                className="inline-flex items-center gap-1.5 rounded-lg border border-white/20 bg-white/5 backdrop-blur-sm px-3 py-1.5 text-sm font-medium text-white hover:bg-white/10 hover:border-white/30 transition-all duration-300"
              >
                <ChevronLeft className="h-4 w-4" />
                Back
              </button>
            </div>

            {/* Interactive Logo */}
            <div 
              className={`flex items-center gap-4 mb-10 transition-all duration-500 delay-100 ${mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}`}
              onMouseEnter={() => setIsLogoHovered(true)}
              onMouseLeave={() => setIsLogoHovered(false)}
            >
              <div 
                className={`relative h-16 w-16 rounded-2xl bg-gradient-to-br from-emerald-400 via-emerald-500 to-teal-600 
                           flex items-center justify-center shadow-lg shadow-emerald-500/25 cursor-pointer
                           transition-all duration-500 ${isLogoHovered ? 'scale-110 rotate-3' : ''}`}
              >
                {/* Animated ring */}
                <div 
                  className={`absolute inset-0 rounded-2xl border-2 border-emerald-400/50 transition-opacity duration-500 ${isLogoHovered ? 'opacity-100' : 'opacity-0'}`}
                  style={{ animation: isLogoHovered ? 'ping-slow 2s cubic-bezier(0, 0, 0.2, 1) infinite' : 'none' }}
                />
                <div className={`absolute -inset-1 rounded-2xl bg-gradient-to-br from-emerald-400 to-teal-500 opacity-0 blur-lg transition-opacity duration-500 ${isLogoHovered ? 'opacity-50' : ''}`} />
                <Sparkles className={`h-8 w-8 text-white relative z-10 transition-all duration-300 ${isLogoHovered ? 'scale-110' : ''}`} />
                {/* Orbiting dots */}
                {isLogoHovered && (
                  <>
                    <div 
                      className="absolute h-2 w-2 rounded-full bg-white"
                      style={{ animation: 'orbit 2s linear infinite' }}
                    />
                    <div 
                      className="absolute h-1.5 w-1.5 rounded-full bg-emerald-300"
                      style={{ animation: 'orbit 3s linear infinite', animationDelay: '0.5s' }}
                    />
                  </>
                )}
              </div>
              <div>
                <span className="font-bold text-4xl text-white tracking-tight">Monty</span>
                <div className="flex items-center gap-2 mt-1">
                  <Zap className="h-3.5 w-3.5 text-emerald-400" />
                  <span className="text-sm text-emerald-400 font-medium">AI-Powered Outreach</span>
                </div>
              </div>
            </div>

            {/* Heading with gradient */}
            <h1 
              className={`text-4xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-white via-slate-200 to-slate-400 mb-4 transition-all duration-500 delay-200 ${mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}`}
            >
              Welcome back
            </h1>
            <p 
              className={`text-lg text-slate-400 leading-relaxed transition-all duration-500 delay-300 ${mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}`}
            >
              Your AI assistant has been busy. Let's see what's new.
            </p>

            {/* Interactive Feature Cards */}
            <div className="mt-10 space-y-3">
              {features.map((feature, i) => (
                <FeatureCard key={feature.title} {...feature} delay={400 + i * 100} />
              ))}
            </div>
          </div>
        </div>

        {/* Right panel - Form */}
        <div className="flex-1 flex items-center justify-center p-8 bg-gradient-to-b from-background to-secondary/20">
          <div className="w-full max-w-md">
            {/* Mobile back */}
            <div className="lg:hidden mb-6">
              <button
                type="button"
                onClick={() => {
                  if (marketingUrl.startsWith('/')) {
                    router.push(marketingUrl);
                    return;
                  }

                  window.location.assign(marketingUrl);
                }}
                className="inline-flex items-center gap-1.5 rounded-lg border border-input bg-background px-3 py-1.5 text-sm font-medium text-foreground hover:bg-secondary transition-colors"
              >
                <ChevronLeft className="h-4 w-4" />
                Back
              </button>
            </div>

            {/* Mobile logo - also interactive */}
            <div className="lg:hidden flex items-center gap-3 mb-8">
              <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-emerald-400 via-emerald-500 to-teal-600 flex items-center justify-center shadow-lg shadow-emerald-500/20">
                <Sparkles className="h-6 w-6 text-white" />
              </div>
              <div>
                <span className="font-bold text-2xl">Monty</span>
                <div className="flex items-center gap-1.5">
                  <Zap className="h-3 w-3 text-emerald-500" />
                  <span className="text-xs text-muted-foreground">AI-Powered</span>
                </div>
              </div>
            </div>

            <div className="mb-8">
              <h2 className="text-2xl font-bold">Sign in to your account</h2>
              <p className="text-muted-foreground mt-2">
                Don't have an account?{' '}
                <Link href="/signup" className="text-primary hover:underline font-medium">
                  Sign up
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
                <label htmlFor="email" className="block text-sm font-medium mb-2">
                  Email
                </label>
                <div className="relative group">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground group-focus-within:text-primary transition-colors" />
                  <input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@company.com"
                    required
                    className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-input bg-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1 focus:border-primary transition-all"
                  />
                </div>
              </div>

              <div>
                <label htmlFor="password" className="block text-sm font-medium mb-2">
                  Password
                </label>
                <div className="relative group">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground group-focus-within:text-primary transition-colors" />
                  <input
                    id="password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    required
                    className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-input bg-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1 focus:border-primary transition-all"
                  />
                </div>
              </div>

              <div className="flex items-center justify-between text-sm">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" className="rounded border-input accent-primary" />
                  <span className="text-muted-foreground">Remember me</span>
                </label>
                <Link href="/forgot-password" className="text-primary hover:underline">
                  Forgot password?
                </Link>
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className="w-full py-2.5 rounded-lg bg-primary text-primary-foreground font-medium 
                         hover:bg-primary/90 hover:shadow-lg hover:shadow-primary/25 
                         transition-all duration-300 disabled:opacity-50 
                         flex items-center justify-center gap-2 group"
              >
                {isLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <>
                    Sign in
                    <ArrowRight className="h-4 w-4 group-hover:translate-x-1 transition-transform" />
                  </>
                )}
              </button>
            </form>

            <div className="relative my-8">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-border" />
              </div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="bg-background px-2 text-muted-foreground">Or continue with</span>
              </div>
            </div>

            <button
              type="button"
              onClick={() => handleOAuth('google')}
              disabled={isLoading}
              className="w-full py-2.5 rounded-lg border border-input bg-background hover:bg-secondary hover:border-primary/20 transition-all duration-300 font-medium flex items-center justify-center gap-3"
            >
              <svg className="h-5 w-5" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
              </svg>
              Continue with Google
            </button>

            <p className="mt-8 text-center text-xs text-muted-foreground">
              By signing in, you agree to our{' '}
              <Link href="/terms" className="underline hover:text-foreground">Terms</Link>
              {' '}and{' '}
              <Link href="/privacy" className="underline hover:text-foreground">Privacy Policy</Link>
            </p>
          </div>
        </div>
      </div>
    </>
  );
}
