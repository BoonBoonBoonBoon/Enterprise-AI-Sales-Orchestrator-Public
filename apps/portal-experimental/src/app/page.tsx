import Link from 'next/link';
import { ArrowRight, Zap, Mail, Users, Brain, Shield, Workflow, MessageSquare } from 'lucide-react';
import AgentNetworkBackground from '@/components/agent-network-background';

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-black text-white overflow-x-hidden font-mono">
      {/* Animated Agent Network Background */}
      <AgentNetworkBackground />

      {/* Content overlay */}
      <div className="relative z-10">
        {/* Header */}
        <header className="fixed top-0 w-full z-50 border-b border-white/5 bg-black/60 backdrop-blur-xl">
          <div className="container flex h-16 items-center justify-between px-6">
            <div className="flex items-center gap-3">
              <div className="relative h-10 w-10 rounded-lg bg-gradient-to-br from-cyan-500 to-purple-600 flex items-center justify-center glow-sm">
                <Zap className="h-5 w-5 text-white" />
                <div className="absolute inset-0 rounded-lg bg-gradient-to-br from-cyan-500 to-purple-600 blur-lg opacity-50" />
              </div>
              <div className="flex flex-col">
                <span className="font-display font-bold text-lg tracking-wider">AGENTIC</span>
                <span className="text-[10px] text-cyan-400/80 tracking-widest">EXPERIMENTAL</span>
              </div>
            </div>
            
            <nav className="hidden md:flex items-center gap-8">
              <Link href="#architecture" className="text-xs text-muted-foreground hover:text-cyan-400 transition-colors uppercase tracking-wider">
                Architecture
              </Link>
              <Link href="#agents" className="text-xs text-muted-foreground hover:text-cyan-400 transition-colors uppercase tracking-wider">
                Agents
              </Link>
              <Link href="#flows" className="text-xs text-muted-foreground hover:text-cyan-400 transition-colors uppercase tracking-wider">
                Flows
              </Link>
              <Link
                href="/demo"
                className="group inline-flex items-center gap-2 rounded border border-cyan-500/50 bg-cyan-500/10 px-4 py-2 text-xs font-medium text-cyan-400 hover:bg-cyan-500/20 transition-all uppercase tracking-wider"
              >
                Launch Demo
                <ArrowRight className="h-3 w-3 group-hover:translate-x-1 transition-transform" />
              </Link>
            </nav>
          </div>
        </header>

        {/* Hero */}
        <section className="pt-40 pb-32 relative">
          <div className="container px-6">
            <div className="max-w-3xl">
              <div className="inline-flex items-center gap-2 rounded border border-emerald-500/30 bg-emerald-500/10 px-4 py-1.5 text-xs mb-8 uppercase tracking-widest">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                </span>
                <span className="text-emerald-400">System Online</span>
              </div>

              <h1 className="text-5xl md:text-7xl font-display font-black tracking-tight mb-6 leading-[0.9]">
                <span className="gradient-text">MULTI-AGENT</span>
                <br />
                <span className="text-white">ORCHESTRATION</span>
              </h1>

              <p className="text-lg text-muted-foreground mb-10 max-w-xl leading-relaxed">
                A 3-tier agent architecture for intelligent B2B email automation. 
                Strategic decisions flow down, results bubble up.
              </p>

              <div className="flex flex-col sm:flex-row gap-4">
                <Link
                  href="/dashboard"
                  className="group inline-flex items-center justify-center gap-3 rounded bg-gradient-to-r from-cyan-500 to-purple-600 px-8 py-4 text-sm font-bold text-white hover:opacity-90 transition-all uppercase tracking-wider glow"
                >
                  Enter Portal
                  <ArrowRight className="h-4 w-4 group-hover:translate-x-1 transition-transform" />
                </Link>
                <Link
                  href="#architecture"
                  className="inline-flex items-center justify-center rounded border border-white/10 bg-white/5 px-8 py-4 text-sm font-medium hover:bg-white/10 transition-colors uppercase tracking-wider"
                >
                  View Architecture
                </Link>
              </div>
            </div>

            {/* Stats row */}
            <div className="mt-20 grid grid-cols-2 md:grid-cols-4 gap-6">
              {[
                { label: 'Agents', value: '6', icon: Brain },
                { label: 'Orchestrators', value: '2', icon: Workflow },
                { label: 'Flows', value: '4', icon: MessageSquare },
                { label: 'Uptime', value: '99.9%', icon: Shield },
              ].map((stat, i) => (
                <div
                  key={i}
                  className="relative p-6 border border-white/5 bg-black/40 backdrop-blur rounded-lg corner-brackets text-cyan-500"
                >
                  <stat.icon className="h-5 w-5 text-cyan-500/50 mb-3" />
                  <div className="text-3xl font-display font-bold text-white mb-1">{stat.value}</div>
                  <div className="text-xs text-muted-foreground uppercase tracking-widest">{stat.label}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Architecture Section */}
        <section id="architecture" className="py-24 border-t border-white/5">
          <div className="container px-6">
            <div className="mb-16">
              <span className="text-xs text-cyan-400 uppercase tracking-widest mb-4 block">// System Design</span>
              <h2 className="text-4xl font-display font-bold mb-4">3-Tier Architecture</h2>
              <p className="text-muted-foreground max-w-2xl">
                Vertical communication only. Orchestrators delegate down, agents execute, results flow up through Redis Streams.
              </p>
            </div>

            <div className="grid md:grid-cols-3 gap-6">
              {[
                {
                  tier: 1,
                  name: 'Strategic Layer',
                  agent: 'Manager Agent',
                  color: '#06b6d4',
                  description: 'Routes high-level goals to orchestrators. Decision-making and intent classification.',
                  icon: Brain,
                },
                {
                  tier: 2,
                  name: 'Business Logic',
                  agent: 'Leads & Outreach Orchestrators',
                  color: '#8b5cf6',
                  description: 'Decomposes workflows into atomic tasks. Context-aware delegation to execution layer.',
                  icon: Workflow,
                },
                {
                  tier: 3,
                  name: 'Execution Layer',
                  agent: 'RAG, Persistence, Copywriter',
                  color: '#10b981',
                  description: 'Performs specialized atomic tasks. Vector search, database ops, AI content generation.',
                  icon: Zap,
                },
              ].map((tier, i) => (
                <div
                  key={i}
                  className="group relative p-8 border border-white/5 bg-black/40 backdrop-blur rounded-lg hover:border-opacity-50 transition-all"
                  style={{ borderColor: `${tier.color}20` }}
                >
                  <div
                    className="absolute inset-0 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity"
                    style={{ background: `radial-gradient(circle at center, ${tier.color}10 0%, transparent 70%)` }}
                  />
                  <div className="relative">
                    <div className="flex items-center gap-3 mb-4">
                      <div
                        className="w-8 h-8 rounded flex items-center justify-center"
                        style={{ backgroundColor: `${tier.color}20`, color: tier.color }}
                      >
                        <tier.icon className="h-4 w-4" />
                      </div>
                      <span className="text-xs font-mono" style={{ color: tier.color }}>
                        TIER {tier.tier}
                      </span>
                    </div>
                    <h3 className="text-xl font-bold mb-2">{tier.name}</h3>
                    <p className="text-sm text-muted-foreground mb-4">{tier.description}</p>
                    <div className="text-xs text-white/50 font-mono">{tier.agent}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Agents Section */}
        <section id="agents" className="py-24 border-t border-white/5">
          <div className="container px-6">
            <div className="mb-16">
              <span className="text-xs text-purple-400 uppercase tracking-widest mb-4 block">// Execution Units</span>
              <h2 className="text-4xl font-display font-bold mb-4">Agent Fleet</h2>
              <p className="text-muted-foreground max-w-2xl">
                Specialized agents handle atomic tasks. Each wrapped in a harness for Redis communication and state management.
              </p>
            </div>

            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
              {[
                { name: 'RAG Agent', role: 'Retrieval', desc: 'Vector search and context retrieval from Supabase', color: '#10b981' },
                { name: 'Persistence Agent', role: 'Storage', desc: 'CRUD operations with RLS-enforced database access', color: '#3b82f6' },
                { name: 'Copywriter Agent', role: 'Generation', desc: 'AI-powered email drafts and personalized content', color: '#f59e0b' },
                { name: 'Leads Orchestrator', role: 'Qualification', desc: 'Lead context building and qualification workflows', color: '#8b5cf6' },
                { name: 'Outreach Orchestrator', role: 'Campaigns', desc: 'Reply generation and campaign sequencing', color: '#ec4899' },
                { name: 'Manager Agent', role: 'Routing', desc: 'Strategic decision-making and intent classification', color: '#06b6d4' },
              ].map((agent, i) => (
                <div
                  key={i}
                  className="group p-5 border border-white/5 bg-black/30 rounded hover:bg-black/50 transition-all cursor-pointer"
                >
                  <div className="flex items-start justify-between mb-3">
                    <div
                      className="px-2 py-0.5 rounded text-[10px] font-mono uppercase tracking-wider"
                      style={{ backgroundColor: `${agent.color}20`, color: agent.color }}
                    >
                      {agent.role}
                    </div>
                    <div className="w-2 h-2 rounded-full" style={{ backgroundColor: agent.color }} />
                  </div>
                  <h3 className="font-bold mb-1">{agent.name}</h3>
                  <p className="text-xs text-muted-foreground">{agent.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* CTA Section */}
        <section className="py-24 border-t border-white/5">
          <div className="container px-6">
            <div className="relative p-12 rounded-xl border border-cyan-500/20 bg-gradient-to-br from-cyan-500/5 to-purple-500/5 overflow-hidden">
              <div className="absolute inset-0 bg-grid opacity-20" />
              <div className="relative text-center max-w-2xl mx-auto">
                <h2 className="text-4xl font-display font-bold mb-4">Ready to orchestrate?</h2>
                <p className="text-muted-foreground mb-8">
                  Experience the power of multi-agent AI systems for your B2B outreach.
                </p>
                <Link
                  href="/dashboard"
                  className="group inline-flex items-center gap-3 rounded bg-white text-black px-8 py-4 text-sm font-bold hover:bg-white/90 transition-all uppercase tracking-wider"
                >
                  Launch Dashboard
                  <ArrowRight className="h-4 w-4 group-hover:translate-x-1 transition-transform" />
                </Link>
              </div>
            </div>
          </div>
        </section>

        {/* Footer */}
        <footer className="py-8 border-t border-white/5">
          <div className="container px-6">
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <div className="font-mono">AGENTIC SYSTEM v2.0 // EXPERIMENTAL</div>
              <div className="flex items-center gap-4">
                <span>[ REDIS STREAMS ]</span>
                <span>[ SUPABASE ]</span>
                <span>[ LANGGRAPH ]</span>
              </div>
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}
