import Link from 'next/link';
import { ArrowLeft, Play, Pause, Activity, Cpu, Database, Mail, Zap } from 'lucide-react';
import AgentNetworkBackground from '@/components/agent-network-background';

export default function DashboardPage() {
  return (
    <div className="min-h-screen bg-black text-white font-mono">
      {/* Background */}
      <AgentNetworkBackground />

      <div className="relative z-10">
        {/* Header */}
        <header className="fixed top-0 w-full z-50 border-b border-white/5 bg-black/80 backdrop-blur-xl">
          <div className="container flex h-14 items-center justify-between px-6">
            <div className="flex items-center gap-4">
              <Link href="/" className="text-muted-foreground hover:text-white transition-colors">
                <ArrowLeft className="h-4 w-4" />
              </Link>
              <div className="flex items-center gap-2">
                <div className="h-8 w-8 rounded bg-gradient-to-br from-cyan-500 to-purple-600 flex items-center justify-center">
                  <Zap className="h-4 w-4 text-white" />
                </div>
                <span className="font-display font-bold tracking-wider">DASHBOARD</span>
              </div>
            </div>

            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2 px-3 py-1.5 rounded border border-emerald-500/30 bg-emerald-500/10">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                </span>
                <span className="text-xs text-emerald-400 uppercase tracking-wider">All Systems Operational</span>
              </div>
            </div>
          </div>
        </header>

        {/* Main content */}
        <main className="pt-24 pb-12 px-6">
          <div className="container">
            {/* Stats Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
              {[
                { label: 'Active Agents', value: '6/6', icon: Cpu, color: '#10b981' },
                { label: 'Messages/min', value: '247', icon: Activity, color: '#3b82f6' },
                { label: 'DB Queries', value: '1.2k', icon: Database, color: '#8b5cf6' },
                { label: 'Emails Processed', value: '89', icon: Mail, color: '#f59e0b' },
              ].map((stat, i) => (
                <div key={i} className="p-4 border border-white/5 bg-black/60 backdrop-blur rounded-lg">
                  <div className="flex items-center gap-2 mb-2">
                    <stat.icon className="h-4 w-4" style={{ color: stat.color }} />
                    <span className="text-xs text-muted-foreground uppercase tracking-wider">{stat.label}</span>
                  </div>
                  <div className="text-2xl font-display font-bold">{stat.value}</div>
                </div>
              ))}
            </div>

            {/* Main panels */}
            <div className="grid md:grid-cols-3 gap-6">
              {/* Live Feed */}
              <div className="md:col-span-2 border border-white/5 bg-black/60 backdrop-blur rounded-lg overflow-hidden">
                <div className="px-4 py-3 border-b border-white/5 flex items-center justify-between">
                  <span className="text-xs uppercase tracking-widest text-cyan-400">// Live Event Stream</span>
                  <div className="flex items-center gap-2">
                    <button className="p-1.5 rounded hover:bg-white/5 transition-colors text-emerald-400">
                      <Play className="h-3 w-3" />
                    </button>
                    <button className="p-1.5 rounded hover:bg-white/5 transition-colors text-muted-foreground">
                      <Pause className="h-3 w-3" />
                    </button>
                  </div>
                </div>
                <div className="p-4 h-80 overflow-y-auto">
                  {[
                    { time: '12:34:56', agent: 'Manager', action: 'Received inbound email from prospect@company.com', type: 'info' },
                    { time: '12:34:57', agent: 'Manager', action: 'Intent classified: REPLY_EMAIL', type: 'decision' },
                    { time: '12:34:57', agent: 'Leads', action: 'Task received: build_reply_context', type: 'task' },
                    { time: '12:34:58', agent: 'RAG', action: 'Querying vector store for lead context...', type: 'work' },
                    { time: '12:34:59', agent: 'RAG', action: 'Retrieved 3 relevant conversation chunks', type: 'success' },
                    { time: '12:35:00', agent: 'Persistence', action: 'Storing message in conversations table', type: 'work' },
                    { time: '12:35:01', agent: 'Outreach', action: 'Generating reply draft...', type: 'task' },
                    { time: '12:35:02', agent: 'Copywriter', action: 'Draft generated: "Thank you for your interest..."', type: 'success' },
                    { time: '12:35:03', agent: 'Manager', action: 'Reply queued for approval', type: 'complete' },
                  ].map((event, i) => (
                    <div key={i} className="flex gap-4 py-2 border-b border-white/5 last:border-0 text-xs">
                      <span className="text-muted-foreground font-mono w-20">{event.time}</span>
                      <span
                        className="w-24 font-medium"
                        style={{
                          color:
                            event.type === 'success' ? '#10b981' :
                            event.type === 'decision' ? '#8b5cf6' :
                            event.type === 'complete' ? '#06b6d4' :
                            event.type === 'task' ? '#f59e0b' :
                            '#666',
                        }}
                      >
                        [{event.agent}]
                      </span>
                      <span className="text-muted-foreground flex-1">{event.action}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Agent Status */}
              <div className="border border-white/5 bg-black/60 backdrop-blur rounded-lg overflow-hidden">
                <div className="px-4 py-3 border-b border-white/5">
                  <span className="text-xs uppercase tracking-widest text-purple-400">// Agent Status</span>
                </div>
                <div className="p-4 space-y-3">
                  {[
                    { name: 'Manager', status: 'active', load: 23 },
                    { name: 'Leads Orch.', status: 'active', load: 45 },
                    { name: 'Outreach Orch.', status: 'active', load: 67 },
                    { name: 'RAG Agent', status: 'active', load: 34 },
                    { name: 'Persistence', status: 'active', load: 89 },
                    { name: 'Copywriter', status: 'idle', load: 12 },
                  ].map((agent, i) => (
                    <div key={i} className="flex items-center justify-between py-2">
                      <div className="flex items-center gap-3">
                        <div
                          className={`w-2 h-2 rounded-full ${agent.status === 'active' ? 'bg-emerald-500' : 'bg-yellow-500'}`}
                        />
                        <span className="text-sm">{agent.name}</span>
                      </div>
                      <div className="flex items-center gap-3">
                        <div className="w-20 h-1.5 bg-white/10 rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full transition-all"
                            style={{
                              width: `${agent.load}%`,
                              backgroundColor: agent.load > 70 ? '#f59e0b' : '#10b981',
                            }}
                          />
                        </div>
                        <span className="text-xs text-muted-foreground w-8">{agent.load}%</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Quick Actions */}
            <div className="mt-8 grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { label: 'Process Inbox', desc: 'Check for new emails' },
                { label: 'Run Campaign', desc: 'Start outreach sequence' },
                { label: 'Sync Leads', desc: 'Update lead database' },
                { label: 'Generate Report', desc: 'Weekly analytics' },
              ].map((action, i) => (
                <button
                  key={i}
                  className="p-4 border border-white/5 bg-black/40 rounded-lg hover:bg-white/5 hover:border-cyan-500/30 transition-all text-left group"
                >
                  <div className="text-sm font-medium group-hover:text-cyan-400 transition-colors">{action.label}</div>
                  <div className="text-xs text-muted-foreground">{action.desc}</div>
                </button>
              ))}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
