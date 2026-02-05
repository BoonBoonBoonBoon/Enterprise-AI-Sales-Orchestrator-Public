import Link from 'next/link';
import {
  ArrowRight,
  CheckCircle2,
  Clock,
  Mail,
  MessageSquare,
  Shield,
  Sparkles,
  Users,
  Zap,
  Building2,
  Star,
} from 'lucide-react';
import FloatingOrbs from '../components/floating-orbs';
import FaqSection from '../components/faq-section';

export default function Page() {
  return (
    <div className="min-h-screen bg-gradient-warm text-foreground overflow-x-hidden">
      {/* Floating background orbs */}
      <FloatingOrbs />

      {/* Hero gradient overlay */}
      <div className="fixed inset-0 bg-gradient-hero pointer-events-none" />

      <div className="relative">
        {/* Header */}
        <header className="sticky top-0 z-50 bg-background/70 backdrop-blur-xl border-b border-border/50">
          <div className="container h-16 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-primary to-purple-600 flex items-center justify-center shadow-lg shadow-primary/20">
                <Sparkles className="h-5 w-5 text-white" />
              </div>
              <span className="font-semibold text-lg">Agentic</span>
            </div>

            <nav className="hidden md:flex items-center gap-8 text-sm">
              <Link href="#how" className="text-muted-foreground hover:text-foreground transition-colors">
                How it works
              </Link>
              <Link href="#benefits" className="text-muted-foreground hover:text-foreground transition-colors">
                Benefits
              </Link>
              <Link href="#faq" className="text-muted-foreground hover:text-foreground transition-colors">
                FAQ
              </Link>
            </nav>

            <div className="flex items-center gap-3">
              <Link
                href="#demo"
                className="hidden sm:inline-flex text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                Log in
              </Link>
              <Link
                href="#demo"
                className="inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2.5 text-sm font-medium text-white hover:bg-primary/90 transition-all shadow-lg shadow-primary/25"
              >
                Get started free
              </Link>
            </div>
          </div>
        </header>

        {/* Hero */}
        <section className="container pt-16 md:pt-24 pb-16">
          <div className="max-w-3xl mx-auto text-center animate-fade-in">
            {/* Trust badge */}
            <div className="inline-flex items-center gap-2 rounded-full bg-green-50 border border-green-200 px-4 py-2 text-sm text-green-700 mb-8">
              <Shield className="h-4 w-4" />
              <span>Trusted by 200+ B2B sales teams</span>
            </div>

            <h1 className="text-4xl md:text-6xl font-bold tracking-tight leading-[1.1] mb-6">
              AI that replies like
              <br />
              <span className="gradient-text-warm">your best sales rep</span>
            </h1>

            <p className="text-xl text-muted-foreground mb-10 max-w-2xl mx-auto leading-relaxed">
              Stop letting leads go cold. Agentic drafts personalized responses in seconds, 
              learns your voice, and keeps you in control of every message.
            </p>

            <div className="flex flex-col sm:flex-row gap-4 justify-center mb-12">
              <Link
                href="#demo"
                className="inline-flex items-center justify-center gap-2 rounded-full bg-primary px-8 py-4 text-base font-medium text-white hover:bg-primary/90 transition-all shadow-xl shadow-primary/30 hover:shadow-2xl hover:shadow-primary/40 hover:-translate-y-0.5"
              >
                Start your free trial
                <ArrowRight className="h-5 w-5" />
              </Link>
              <Link
                href="#how"
                className="inline-flex items-center justify-center rounded-full border-2 border-border bg-white/50 px-8 py-4 text-base font-medium hover:bg-white hover:border-primary/30 transition-all"
              >
                See how it works
              </Link>
            </div>

            {/* Social proof row */}
            <div className="flex flex-wrap items-center justify-center gap-6 text-sm text-muted-foreground">
              <div className="flex items-center gap-2">
                <div className="flex -space-x-2">
                  {[1, 2, 3, 4].map((i) => (
                    <div
                      key={i}
                      className="h-8 w-8 rounded-full bg-gradient-to-br from-blue-400 to-purple-500 border-2 border-white"
                    />
                  ))}
                </div>
                <span>1,200+ users</span>
              </div>
              <div className="flex items-center gap-1.5">
                {[1, 2, 3, 4, 5].map((i) => (
                  <Star key={i} className="h-4 w-4 fill-yellow-400 text-yellow-400" />
                ))}
                <span className="ml-1">4.9/5 rating</span>
              </div>
            </div>
          </div>

          {/* Dashboard preview */}
          <div className="mt-16 max-w-4xl mx-auto">
            <div className="card-soft p-2 animate-fade-in" style={{ animationDelay: '0.2s' }}>
              <div className="rounded-xl bg-muted/30 p-6 md:p-8 min-h-[320px] flex flex-col">
                {/* Mock inbox header */}
                <div className="flex items-center justify-between mb-6">
                  <div className="flex items-center gap-3">
                    <Mail className="h-5 w-5 text-primary" />
                    <span className="font-medium">Inbox</span>
                    <span className="px-2 py-0.5 rounded-full bg-primary/10 text-primary text-xs font-medium">
                      3 drafts ready
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Clock className="h-3.5 w-3.5" />
                    <span>Updated 2 min ago</span>
                  </div>
                </div>

                {/* Mock email items */}
                <div className="space-y-3 flex-1">
                  {[
                    { from: 'Sarah Chen', subject: 'Re: Pricing question', status: 'draft', time: '2m' },
                    { from: 'Marcus Johnson', subject: 'Following up on demo', status: 'draft', time: '5m' },
                    { from: 'Elena Rodriguez', subject: 'Partnership inquiry', status: 'draft', time: '12m' },
                  ].map((email, i) => (
                    <div
                      key={i}
                      className="flex items-center gap-4 p-4 rounded-lg bg-white border border-border/60 hover:border-primary/30 transition-colors cursor-pointer"
                    >
                      <div className="h-10 w-10 rounded-full bg-gradient-to-br from-blue-400 to-purple-500 flex items-center justify-center text-white text-sm font-medium">
                        {email.from.split(' ').map(n => n[0]).join('')}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-medium truncate">{email.from}</span>
                          <span className="text-xs text-muted-foreground">{email.time}</span>
                        </div>
                        <div className="text-sm text-muted-foreground truncate">{email.subject}</div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="px-2.5 py-1 rounded-full bg-amber-50 text-amber-700 text-xs font-medium border border-amber-200">
                          AI Draft Ready
                        </span>
                        <button className="px-3 py-1.5 rounded-lg bg-primary text-white text-xs font-medium hover:bg-primary/90 transition-colors">
                          Review
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* How it works */}
        <section id="how" className="container py-20">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">
              Three steps to faster replies
            </h2>
            <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
              No complex setup. No learning curve. Just connect and let AI handle the heavy lifting.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {[
              {
                step: '01',
                icon: Mail,
                title: 'Connect your inbox',
                description: 'Link Gmail, Outlook, or any email provider. Takes less than 2 minutes. We only read what you authorize.',
              },
              {
                step: '02',
                icon: Sparkles,
                title: 'AI drafts responses',
                description: 'Our AI reads incoming emails, pulls context from your CRM, and writes personalized replies that match your tone.',
              },
              {
                step: '03',
                icon: CheckCircle2,
                title: 'You review & send',
                description: 'Every draft waits for your approval. Edit if needed, then send with one click. You stay in complete control.',
              },
            ].map((item, i) => (
              <div key={i} className="relative">
                <div className="card-soft p-8 h-full transition-all hover:-translate-y-1">
                  <div className="flex items-center gap-4 mb-6">
                    <div className="h-12 w-12 rounded-xl bg-primary/10 flex items-center justify-center">
                      <item.icon className="h-6 w-6 text-primary" />
                    </div>
                    <span className="text-4xl font-bold text-muted-foreground/20">{item.step}</span>
                  </div>
                  <h3 className="text-xl font-semibold mb-3">{item.title}</h3>
                  <p className="text-muted-foreground leading-relaxed">{item.description}</p>
                </div>

                {i < 2 && (
                  <div className="hidden md:block absolute top-1/2 -right-4 w-8 h-0.5 bg-border" />
                )}
              </div>
            ))}
          </div>
        </section>

        {/* Benefits */}
        <section id="benefits" className="container py-20">
          <div className="grid lg:grid-cols-2 gap-16 items-center">
            <div>
              <h2 className="text-3xl md:text-4xl font-bold mb-6">
                Why B2B teams choose Agentic
              </h2>
              <p className="text-lg text-muted-foreground mb-10">
                We built this for busy sales teams who want AI that actually helps—
                without the learning curve or risk.
              </p>

              <div className="space-y-6">
                {[
                  {
                    icon: Clock,
                    title: 'Save 10+ hours per week',
                    description: 'Stop typing the same replies. AI handles the routine so you focus on closing.',
                  },
                  {
                    icon: Users,
                    title: 'Personalize at scale',
                    description: 'Every reply references past conversations and CRM data. No more generic templates.',
                  },
                  {
                    icon: Shield,
                    title: 'Stay compliant & secure',
                    description: 'SOC 2 compliant, GDPR ready. Your data never trains external models.',
                  },
                  {
                    icon: MessageSquare,
                    title: 'Sound like you, not a bot',
                    description: 'AI learns your writing style. Customers won\'t know it\'s AI-assisted.',
                  },
                ].map((item, i) => (
                  <div key={i} className="flex gap-4">
                    <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
                      <item.icon className="h-5 w-5 text-primary" />
                    </div>
                    <div>
                      <h4 className="font-semibold mb-1">{item.title}</h4>
                      <p className="text-muted-foreground text-sm">{item.description}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="card-soft p-8">
              <div className="flex items-center gap-4 mb-6">
                <div className="h-14 w-14 rounded-full bg-gradient-to-br from-blue-400 to-purple-500" />
                <div>
                  <div className="font-semibold">Jessica Park</div>
                  <div className="text-sm text-muted-foreground">VP Sales, TechCorp</div>
                </div>
              </div>
              <blockquote className="text-lg leading-relaxed mb-6">
                "We went from 4-hour response times to under 30 minutes. Our team saves hours every day, 
                and prospects actually notice how personal our follow-ups feel. 
                <span className="font-medium text-primary"> It's like having 3 extra SDRs.</span>"
              </blockquote>
              <div className="flex items-center gap-4 pt-6 border-t border-border">
                <div className="flex items-center gap-1">
                  {[1, 2, 3, 4, 5].map((i) => (
                    <Star key={i} className="h-4 w-4 fill-yellow-400 text-yellow-400" />
                  ))}
                </div>
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Building2 className="h-4 w-4" />
                  <span>50-person sales team</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Stats */}
        <section className="container py-16">
          <div className="card-soft p-10 bg-gradient-to-br from-primary/5 to-purple-500/5">
            <div className="grid md:grid-cols-4 gap-8 text-center">
              {[
                { value: '73%', label: 'Faster response times' },
                { value: '10+', label: 'Hours saved per week' },
                { value: '94%', label: 'Customer satisfaction' },
                { value: '3x', label: 'More leads handled' },
              ].map((stat, i) => (
                <div key={i}>
                  <div className="text-4xl md:text-5xl font-bold gradient-text-warm mb-2">{stat.value}</div>
                  <div className="text-muted-foreground">{stat.label}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* FAQ */}
        <section id="faq" className="container py-20">
          <div className="max-w-3xl mx-auto">
            <div className="text-center mb-12">
              <h2 className="text-3xl md:text-4xl font-bold mb-4">
                Questions? We've got answers.
              </h2>
              <p className="text-lg text-muted-foreground">
                Everything you need to know about getting started with AI email automation.
              </p>
            </div>

            <FaqSection />
          </div>
        </section>

        {/* CTA */}
        <section id="demo" className="container py-20">
          <div className="card-soft p-10 md:p-16 text-center bg-gradient-to-br from-primary/5 via-transparent to-purple-500/5">
            <div className="inline-flex items-center gap-2 rounded-full bg-primary/10 border border-primary/20 px-4 py-2 text-sm text-primary font-medium mb-6">
              <Zap className="h-4 w-4" />
              <span>No credit card required</span>
            </div>

            <h2 className="text-3xl md:text-4xl font-bold mb-4">
              Ready to reply faster?
            </h2>
            <p className="text-lg text-muted-foreground mb-10 max-w-xl mx-auto">
              Join 200+ B2B teams already saving hours every week. 
              Start your free trial today—setup takes 2 minutes.
            </p>

            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Link
                href="#"
                className="inline-flex items-center justify-center gap-2 rounded-full bg-primary px-8 py-4 text-base font-medium text-white hover:bg-primary/90 transition-all shadow-xl shadow-primary/30"
              >
                Start free trial
                <ArrowRight className="h-5 w-5" />
              </Link>
              <Link
                href="#"
                className="inline-flex items-center justify-center rounded-full border-2 border-border bg-white px-8 py-4 text-base font-medium hover:border-primary/30 transition-all"
              >
                Schedule a demo
              </Link>
            </div>

            <p className="mt-6 text-sm text-muted-foreground">
              Free 14-day trial • Cancel anytime • Setup in 2 minutes
            </p>
          </div>
        </section>

        {/* Footer */}
        <footer className="border-t border-border py-10">
          <div className="container">
            <div className="flex flex-col md:flex-row items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-primary to-purple-600 flex items-center justify-center">
                  <Sparkles className="h-4 w-4 text-white" />
                </div>
                <span className="font-semibold">Agentic</span>
              </div>

              <div className="flex items-center gap-6 text-sm text-muted-foreground">
                <Link href="#" className="hover:text-foreground transition-colors">Privacy</Link>
                <Link href="#" className="hover:text-foreground transition-colors">Terms</Link>
                <Link href="#" className="hover:text-foreground transition-colors">Security</Link>
                <Link href="#" className="hover:text-foreground transition-colors">Contact</Link>
              </div>

              <div className="text-sm text-muted-foreground">
                © 2026 Agentic. All rights reserved.
              </div>
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}
