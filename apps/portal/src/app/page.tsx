import Link from 'next/link';
import { ArrowRight, Zap, Shield, BarChart3, Mail } from 'lucide-react';

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="fixed top-0 w-full z-50 border-b border-border/40 bg-background/80 backdrop-blur-xl">
        <div className="container flex h-16 items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
              <Zap className="h-5 w-5 text-white" />
            </div>
            <span className="font-bold text-xl">Agentic</span>
          </div>
          <nav className="hidden md:flex items-center gap-6">
            <Link href="#features" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
              Features
            </Link>
            <Link href="#pricing" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
              Pricing
            </Link>
            <Link href="/login" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
              Login
            </Link>
            <Link
              href="/login"
              className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
            >
              Get Started
            </Link>
          </nav>
        </div>
      </header>

      {/* Hero */}
      <section className="pt-32 pb-20 relative overflow-hidden">
        {/* Background effects */}
        <div className="absolute inset-0 bg-grid opacity-50" />
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-blue-500/20 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-purple-500/20 rounded-full blur-3xl" />

        <div className="container relative">
          <div className="max-w-3xl mx-auto text-center">
            <div className="inline-flex items-center gap-2 rounded-full border border-border/60 bg-muted/30 px-4 py-1.5 text-sm mb-6">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
              </span>
              AI-Powered Email Automation
            </div>
            
            <h1 className="text-4xl md:text-6xl font-bold tracking-tight mb-6">
              <span className="gradient-text">Intelligent Outreach</span>
              <br />
              with Human Control
            </h1>
            
            <p className="text-lg text-muted-foreground mb-8 max-w-2xl mx-auto">
              Automate your B2B email replies with AI-generated responses, context-aware personalization, 
              and approval workflows that keep you in control.
            </p>
            
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Link
                href="/login"
                className="inline-flex items-center justify-center gap-2 rounded-md bg-primary px-6 py-3 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-all hover:gap-3"
              >
                Start Free Trial
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                href="#demo"
                className="inline-flex items-center justify-center rounded-md border border-border px-6 py-3 text-sm font-medium hover:bg-muted transition-colors"
              >
                Watch Demo
              </Link>
            </div>
          </div>

          {/* Dashboard Preview */}
          <div className="mt-16 relative">
            <div className="absolute inset-0 bg-gradient-to-t from-background via-transparent to-transparent z-10 pointer-events-none" />
            <div className="rounded-xl border border-border/60 bg-card/50 backdrop-blur overflow-hidden shadow-2xl">
              <div className="h-8 bg-muted/50 border-b border-border/40 flex items-center gap-2 px-4">
                <div className="h-3 w-3 rounded-full bg-red-500/80" />
                <div className="h-3 w-3 rounded-full bg-yellow-500/80" />
                <div className="h-3 w-3 rounded-full bg-green-500/80" />
              </div>
              <div className="p-6 h-80 flex items-center justify-center text-muted-foreground">
                <div className="text-center">
                  <Mail className="h-16 w-16 mx-auto mb-4 opacity-50" />
                  <p className="text-sm">Dashboard Preview</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="py-20 border-t border-border/40">
        <div className="container">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold mb-4">Everything you need for intelligent outreach</h2>
            <p className="text-muted-foreground max-w-2xl mx-auto">
              AI-powered automation with the control and visibility your team needs.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            <div className="rounded-xl border border-border/60 bg-card/30 p-6 hover:border-primary/50 transition-colors">
              <div className="h-12 w-12 rounded-lg bg-blue-500/10 flex items-center justify-center mb-4">
                <Mail className="h-6 w-6 text-blue-500" />
              </div>
              <h3 className="font-semibold text-lg mb-2">Smart Drafts</h3>
              <p className="text-sm text-muted-foreground">
                AI generates context-aware reply drafts using your lead data and conversation history.
              </p>
            </div>

            <div className="rounded-xl border border-border/60 bg-card/30 p-6 hover:border-primary/50 transition-colors">
              <div className="h-12 w-12 rounded-lg bg-purple-500/10 flex items-center justify-center mb-4">
                <Shield className="h-6 w-6 text-purple-500" />
              </div>
              <h3 className="font-semibold text-lg mb-2">Approval Workflows</h3>
              <p className="text-sm text-muted-foreground">
                Review, edit, and approve every outbound message. Auto-send when you're ready.
              </p>
            </div>

            <div className="rounded-xl border border-border/60 bg-card/30 p-6 hover:border-primary/50 transition-colors">
              <div className="h-12 w-12 rounded-lg bg-cyan-500/10 flex items-center justify-center mb-4">
                <BarChart3 className="h-6 w-6 text-cyan-500" />
              </div>
              <h3 className="font-semibold text-lg mb-2">Full Visibility</h3>
              <p className="text-sm text-muted-foreground">
                Track metrics, browse conversations, and manage your leads database in one place.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 border-t border-border/40">
        <div className="container flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="h-6 w-6 rounded bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
              <Zap className="h-4 w-4 text-white" />
            </div>
            <span className="font-semibold">Agentic</span>
          </div>
          <p className="text-sm text-muted-foreground">
            © 2026 Agentic. All rights reserved.
          </p>
        </div>
      </footer>
    </div>
  );
}
