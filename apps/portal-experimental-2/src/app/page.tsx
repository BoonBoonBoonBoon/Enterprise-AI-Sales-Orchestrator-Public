import Link from 'next/link';
import ArchitectureVisual from '../components/architecture-visual';
import { ArrowRight, CheckCircle2, Shield, Workflow, Zap } from 'lucide-react';

export default function Page() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Top background */}
      <div className="absolute inset-0 bg-grid-subtle opacity-20" />
      <div className="absolute inset-0 bg-radial-soft" />

      <div className="relative">
        {/* Header */}
        <header className="sticky top-0 z-50 border-b border-border bg-background/70 backdrop-blur-xl">
          <div className="container h-16 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="h-9 w-9 rounded-lg bg-primary/15 border border-primary/25 flex items-center justify-center">
                <Zap className="h-4 w-4 text-primary" />
              </div>
              <div className="leading-tight">
                <div className="font-semibold">Agentic</div>
                <div className="text-[11px] font-mono text-muted-foreground tracking-widest">EXPERIMENTAL / MARKETING v2</div>
              </div>
            </div>

            <nav className="hidden md:flex items-center gap-6 text-sm">
              <Link href="#how" className="text-muted-foreground hover:text-foreground transition-colors">How it works</Link>
              <Link href="#trust" className="text-muted-foreground hover:text-foreground transition-colors">Trust</Link>
              <Link href="#architecture" className="text-muted-foreground hover:text-foreground transition-colors">Architecture</Link>
              <Link
                href="#cta"
                className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 transition-opacity"
              >
                Request access
                <ArrowRight className="h-4 w-4" />
              </Link>
            </nav>
          </div>
        </header>

        {/* Hero */}
        <section className="container pt-14 md:pt-20 pb-10">
          <div className="grid lg:grid-cols-2 gap-10 items-start">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-border bg-card/50 px-4 py-1.5 text-xs text-muted-foreground">
                <span className="h-2 w-2 rounded-full bg-primary animate-breathe" />
                Human-in-the-loop AI email automation
              </div>

              <h1 className="mt-6 text-4xl md:text-5xl font-semibold tracking-tight">
                Reply faster with <span className="gradient-text-soft">agent orchestration</span>,
                <br className="hidden md:block" /> without losing control.
              </h1>

              <p className="mt-5 text-lg text-muted-foreground max-w-xl">
                A calm, reliable system that triages inbound messages, pulls context, drafts responses, and routes approvals—
                all through a strict 3-tier agent architecture.
              </p>

              <div className="mt-8 flex flex-col sm:flex-row gap-3">
                <Link
                  href="#cta"
                  className="inline-flex items-center justify-center gap-2 rounded-md bg-primary px-6 py-3 text-sm font-medium text-primary-foreground hover:opacity-90 transition-opacity"
                >
                  Get a guided demo
                  <ArrowRight className="h-4 w-4" />
                </Link>
                <Link
                  href="#architecture"
                  className="inline-flex items-center justify-center rounded-md border border-border bg-card/40 px-6 py-3 text-sm font-medium hover:bg-card/60 transition-colors"
                >
                  See the architecture
                </Link>
              </div>

              <div className="mt-8 grid gap-2 text-sm">
                {["Fewer missed opportunities", "Consistent tone at scale", "Audit-friendly decisions"].map((x) => (
                  <div key={x} className="flex items-center gap-2 text-muted-foreground">
                    <CheckCircle2 className="h-4 w-4 text-primary" />
                    <span>{x}</span>
                  </div>
                ))}
              </div>
            </div>

            <div id="architecture" className="lg:pt-2">
              <ArchitectureVisual />
            </div>
          </div>
        </section>

        {/* How */}
        <section id="how" className="container py-12">
          <div className="grid md:grid-cols-3 gap-6">
            {[{
              icon: Workflow,
              title: 'Route the right work',
              body: 'Manager classifies intent and delegates vertically—no cross-orchestrator chaos.',
            }, {
              icon: Shield,
              title: 'Make it governable',
              body: 'Clear responsibility boundaries, audit-friendly events, predictable execution.',
            }, {
              icon: Zap,
              title: 'Ship speed safely',
              body: 'Draft replies fast, surface context, and keep approvals in the loop.',
            }].map((card) => (
              <div key={card.title} className="glass-soft rounded-xl p-6">
                <div className="h-10 w-10 rounded-lg bg-primary/15 border border-primary/25 flex items-center justify-center">
                  <card.icon className="h-5 w-5 text-primary" />
                </div>
                <h3 className="mt-4 font-semibold">{card.title}</h3>
                <p className="mt-2 text-sm text-muted-foreground">{card.body}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Trust */}
        <section id="trust" className="container py-12">
          <div className="glass-soft rounded-2xl p-8 md:p-10">
            <div className="grid lg:grid-cols-2 gap-10 items-start">
              <div>
                <div className="text-xs font-mono text-muted-foreground tracking-widest">// TRUST SIGNALS</div>
                <h2 className="mt-3 text-2xl md:text-3xl font-semibold">Designed for reliability, not demos.</h2>
                <p className="mt-3 text-muted-foreground">
                  Calm visuals, clear claims. The goal is confidence: predictable routing, safe delegation, and control points.
                </p>
              </div>
              <div className="grid gap-3 text-sm text-muted-foreground">
                {["Strict tier boundaries (vertical only)", "Centralized orchestration decisions", "Clear infra dependencies", "Simple-to-explain system map"].map((x) => (
                  <div key={x} className="flex items-start gap-2">
                    <span className="mt-1 h-1.5 w-1.5 rounded-full bg-primary" />
                    <span>{x}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* CTA */}
        <section id="cta" className="container py-14">
          <div className="rounded-2xl border border-border bg-card/60 p-8 md:p-10 shadow-soft">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6">
              <div>
                <h3 className="text-2xl font-semibold">Want this for your inbox?</h3>
                <p className="mt-2 text-muted-foreground">We’ll walk through your flows and map agents to your process.</p>
              </div>
              <div className="flex gap-3">
                <Link
                  href="#"
                  className="inline-flex items-center justify-center rounded-md bg-primary px-6 py-3 text-sm font-medium text-primary-foreground hover:opacity-90 transition-opacity"
                >
                  Book a call
                </Link>
                <Link
                  href="#"
                  className="inline-flex items-center justify-center rounded-md border border-border bg-background/20 px-6 py-3 text-sm font-medium hover:bg-background/30 transition-colors"
                >
                  Email us
                </Link>
              </div>
            </div>
          </div>
        </section>

        <footer className="border-t border-border py-8">
          <div className="container text-xs text-muted-foreground flex items-center justify-between">
            <div className="font-mono">AGENTIC / EXPERIMENTAL-2</div>
            <div className="font-mono">[ calm architecture viz ]</div>
          </div>
        </footer>
      </div>
    </div>
  );
}
