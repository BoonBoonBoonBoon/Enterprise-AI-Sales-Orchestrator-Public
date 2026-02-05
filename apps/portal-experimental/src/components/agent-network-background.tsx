'use client';

import { useState, useEffect, useCallback } from 'react';

interface Agent {
  id: string;
  name: string;
  tier: number;
  x: number;
  y: number;
  type: 'manager' | 'orchestrator' | 'agent' | 'infra';
  description: string;
  connections: string[];
}

interface Flow {
  id: string;
  name: string;
  color: string;
  path: string[];
}

const agents: Record<string, Agent> = {
  manager: {
    id: 'manager',
    name: 'Manager',
    tier: 1,
    x: 50,
    y: 12,
    type: 'manager',
    description: 'Strategic Decision & Routing',
    connections: ['leads', 'outreach'],
  },
  leads: {
    id: 'leads',
    name: 'Leads Orchestrator',
    tier: 2,
    x: 30,
    y: 35,
    type: 'orchestrator',
    description: 'Lead Qualification & Context',
    connections: ['manager', 'rag', 'persistence'],
  },
  outreach: {
    id: 'outreach',
    name: 'Outreach Orchestrator',
    tier: 2,
    x: 70,
    y: 35,
    type: 'orchestrator',
    description: 'Campaign & Reply Workflows',
    connections: ['manager', 'copywriter', 'persistence'],
  },
  rag: {
    id: 'rag',
    name: 'RAG Agent',
    tier: 3,
    x: 15,
    y: 60,
    type: 'agent',
    description: 'Vector Search & Retrieval',
    connections: ['leads', 'vector'],
  },
  persistence: {
    id: 'persistence',
    name: 'Persistence Agent',
    tier: 3,
    x: 50,
    y: 60,
    type: 'agent',
    description: 'Database CRUD Operations',
    connections: ['leads', 'outreach', 'supabase'],
  },
  copywriter: {
    id: 'copywriter',
    name: 'Copywriter Agent',
    tier: 3,
    x: 85,
    y: 60,
    type: 'agent',
    description: 'AI Content Generation',
    connections: ['outreach'],
  },
  redis: {
    id: 'redis',
    name: 'Redis Streams',
    tier: 4,
    x: 30,
    y: 85,
    type: 'infra',
    description: 'Async Communication',
    connections: ['manager', 'leads', 'outreach'],
  },
  supabase: {
    id: 'supabase',
    name: 'Supabase',
    tier: 4,
    x: 50,
    y: 85,
    type: 'infra',
    description: 'PostgreSQL + Auth + RLS',
    connections: ['persistence'],
  },
  vector: {
    id: 'vector',
    name: 'Vector DB',
    tier: 4,
    x: 70,
    y: 85,
    type: 'infra',
    description: 'Embeddings & Similarity',
    connections: ['rag'],
  },
};

const flows: Flow[] = [
  {
    id: 'inbound-email',
    name: 'Inbound Email',
    color: '#10b981',
    path: ['manager', 'leads', 'rag', 'persistence', 'outreach', 'copywriter'],
  },
  {
    id: 'lead-enrichment',
    name: 'Lead Enrichment',
    color: '#3b82f6',
    path: ['manager', 'leads', 'rag', 'persistence'],
  },
  {
    id: 'campaign-outreach',
    name: 'Campaign Outreach',
    color: '#f59e0b',
    path: ['manager', 'outreach', 'copywriter', 'persistence'],
  },
  {
    id: 'reply-generation',
    name: 'Reply Generation',
    color: '#a855f7',
    path: ['manager', 'leads', 'outreach', 'copywriter'],
  },
];

export default function AgentNetworkBackground() {
  const [activeFlow, setActiveFlow] = useState<string | null>(null);
  const [hoveredAgent, setHoveredAgent] = useState<string | null>(null);
  const [particles, setParticles] = useState<{ id: string; x: number; y: number; progress: number; flowId: string }[]>([]);

  // Auto-cycle through flows
  useEffect(() => {
    const interval = setInterval(() => {
      if (!hoveredAgent) {
        const randomFlow = flows[Math.floor(Math.random() * flows.length)];
        setActiveFlow(randomFlow.id);
      }
    }, 4000);
    return () => clearInterval(interval);
  }, [hoveredAgent]);

  // Animate particles along active flow
  useEffect(() => {
    if (!activeFlow) return;

    const flow = flows.find((f) => f.id === activeFlow);
    if (!flow) return;

    const interval = setInterval(() => {
      setParticles((prev) => {
        // Add new particle
        const newParticle = {
          id: `${Date.now()}-${Math.random()}`,
          x: agents[flow.path[0]].x,
          y: agents[flow.path[0]].y,
          progress: 0,
          flowId: activeFlow,
        };

        // Update existing particles
        const updated = prev
          .map((p) => ({ ...p, progress: p.progress + 0.02 }))
          .filter((p) => p.progress < 1);

        return [...updated, newParticle].slice(-10);
      });
    }, 300);

    return () => clearInterval(interval);
  }, [activeFlow]);

  const getPath = useCallback((from: string, to: string) => {
    const fromAgent = agents[from];
    const toAgent = agents[to];
    if (!fromAgent || !toAgent) return '';

    const x1 = fromAgent.x;
    const y1 = fromAgent.y;
    const x2 = toAgent.x;
    const y2 = toAgent.y;

    const midX = (x1 + x2) / 2;
    const midY = (y1 + y2) / 2;
    const curve = Math.abs(y2 - y1) * 0.2;

    return `M ${x1} ${y1} Q ${midX} ${midY - curve} ${x2} ${y2}`;
  }, []);

  const isConnectionActive = useCallback(
    (from: string, to: string) => {
      if (!activeFlow) return false;
      const flow = flows.find((f) => f.id === activeFlow);
      if (!flow) return false;

      for (let i = 0; i < flow.path.length - 1; i++) {
        if (flow.path[i] === from && flow.path[i + 1] === to) return true;
        if (flow.path[i] === to && flow.path[i + 1] === from) return true;
      }
      return false;
    },
    [activeFlow]
  );

  const activeFlowColor = activeFlow ? flows.find((f) => f.id === activeFlow)?.color : null;

  const getAgentColor = (type: Agent['type']) => {
    switch (type) {
      case 'manager':
        return '#06b6d4';
      case 'orchestrator':
        return '#8b5cf6';
      case 'agent':
        return '#10b981';
      case 'infra':
        return '#64748b';
      default:
        return '#666';
    }
  };

  return (
    <div className="fixed inset-0 overflow-hidden pointer-events-none">
      {/* Grid background */}
      <div className="absolute inset-0 bg-grid opacity-30" />

      {/* Scan line effect */}
      <div className="scan-line" />

      {/* Gradient overlays */}
      <div className="absolute top-0 left-0 w-full h-32 bg-gradient-to-b from-black to-transparent z-10" />
      <div className="absolute bottom-0 left-0 w-full h-32 bg-gradient-to-t from-black to-transparent z-10" />

      {/* SVG Network */}
      <svg className="w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="xMidYMid slice">
        <defs>
          <filter id="glow">
            <feGaussianBlur stdDeviation="1" result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>

          <linearGradient id="flowGradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor={activeFlowColor || '#06b6d4'} stopOpacity="0" />
            <stop offset="50%" stopColor={activeFlowColor || '#06b6d4'} stopOpacity="1" />
            <stop offset="100%" stopColor={activeFlowColor || '#06b6d4'} stopOpacity="0" />
          </linearGradient>

          <radialGradient id="nodeGlow">
            <stop offset="0%" stopColor={activeFlowColor || '#06b6d4'} stopOpacity="0.4" />
            <stop offset="100%" stopColor={activeFlowColor || '#06b6d4'} stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* Draw connections */}
        {Object.entries(agents).map(([key, agent]) =>
          agent.connections?.map((target) => {
            const isActive = isConnectionActive(key, target);
            const isHovered = hoveredAgent === key || hoveredAgent === target;

            return (
              <g key={`${key}-${target}`}>
                <path
                  d={getPath(key, target)}
                  fill="none"
                  stroke={isActive ? activeFlowColor || '#06b6d4' : isHovered ? '#444' : '#222'}
                  strokeWidth={isActive ? 0.3 : 0.1}
                  opacity={isActive ? 0.8 : isHovered ? 0.6 : 0.3}
                  style={{ transition: 'all 0.5s ease' }}
                />

                {/* Animated flow particles */}
                {isActive && (
                  <>
                    <circle r="0.4" fill={activeFlowColor || '#06b6d4'} filter="url(#glow)">
                      <animateMotion dur="2s" repeatCount="indefinite" path={getPath(key, target)} />
                    </circle>
                    <circle r="0.3" fill={activeFlowColor || '#06b6d4'} filter="url(#glow)">
                      <animateMotion dur="2s" repeatCount="indefinite" begin="0.5s" path={getPath(key, target)} />
                    </circle>
                  </>
                )}
              </g>
            );
          })
        )}

        {/* Draw agent nodes */}
        {Object.entries(agents).map(([key, agent]) => {
          const isInActiveFlow = activeFlow && flows.find((f) => f.id === activeFlow)?.path.includes(key);
          const nodeColor = isInActiveFlow ? activeFlowColor : getAgentColor(agent.type);

          return (
            <g key={key}>
              {/* Outer glow */}
              {isInActiveFlow && <circle cx={agent.x} cy={agent.y} r="4" fill="url(#nodeGlow)" opacity="0.5">
                <animate attributeName="r" values="3;5;3" dur="2s" repeatCount="indefinite" />
              </circle>}

              {/* Node circle */}
              <circle
                cx={agent.x}
                cy={agent.y}
                r="2"
                fill="black"
                stroke={nodeColor || '#666'}
                strokeWidth="0.2"
                filter={isInActiveFlow ? 'url(#glow)' : undefined}
                style={{ transition: 'all 0.3s ease' }}
              />

              {/* Inner dot */}
              <circle
                cx={agent.x}
                cy={agent.y}
                r="0.6"
                fill={nodeColor || '#666'}
                opacity={isInActiveFlow ? 1 : 0.6}
              >
                {isInActiveFlow && (
                  <animate attributeName="opacity" values="0.6;1;0.6" dur="1s" repeatCount="indefinite" />
                )}
              </circle>

              {/* Label */}
              <text
                x={agent.x}
                y={agent.y + 4.5}
                textAnchor="middle"
                fill={isInActiveFlow ? nodeColor || '#06b6d4' : '#666'}
                fontSize="1.2"
                fontFamily="JetBrains Mono, monospace"
                opacity={isInActiveFlow ? 1 : 0.5}
                style={{ transition: 'all 0.3s ease' }}
              >
                {agent.name.toUpperCase()}
              </text>

              {/* Tier indicator */}
              <text
                x={agent.x}
                y={agent.y - 3.5}
                textAnchor="middle"
                fill="#444"
                fontSize="0.8"
                fontFamily="JetBrains Mono, monospace"
              >
                T{agent.tier}
              </text>
            </g>
          );
        })}

        {/* Tier labels */}
        <text x="3" y="10" fill="#333" fontSize="1" fontFamily="JetBrains Mono, monospace">
          // TIER 1: STRATEGIC
        </text>
        <text x="3" y="33" fill="#333" fontSize="1" fontFamily="JetBrains Mono, monospace">
          // TIER 2: ORCHESTRATION
        </text>
        <text x="3" y="58" fill="#333" fontSize="1" fontFamily="JetBrains Mono, monospace">
          // TIER 3: EXECUTION
        </text>
        <text x="3" y="83" fill="#333" fontSize="1" fontFamily="JetBrains Mono, monospace">
          // TIER 4: INFRASTRUCTURE
        </text>
      </svg>

      {/* Flow indicator */}
      <div className="absolute bottom-8 left-1/2 -translate-x-1/2 flex gap-3 pointer-events-auto z-20">
        {flows.map((flow) => (
          <button
            key={flow.id}
            onClick={() => setActiveFlow(activeFlow === flow.id ? null : flow.id)}
            className="px-3 py-1.5 text-[10px] font-mono border transition-all hover:scale-105 uppercase tracking-wider"
            style={{
              borderColor: activeFlow === flow.id ? flow.color : '#333',
              backgroundColor: activeFlow === flow.id ? `${flow.color}20` : 'transparent',
              color: activeFlow === flow.id ? flow.color : '#666',
            }}
          >
            {flow.name}
          </button>
        ))}
      </div>
    </div>
  );
}
