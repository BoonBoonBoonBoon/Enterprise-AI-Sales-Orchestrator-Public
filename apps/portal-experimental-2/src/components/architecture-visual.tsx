'use client';

import { useEffect, useMemo, useState } from 'react';

type NodeType = 'tier1' | 'tier2' | 'tier3' | 'infra';

interface ArchNode {
  id: string;
  label: string;
  type: NodeType;
  x: number;
  y: number;
  links: string[];
}

interface Flow {
  id: string;
  name: string;
  colorVar: '--viz-a' | '--viz-b' | '--viz-c';
  path: string[];
}

const nodes: Record<string, ArchNode> = {
  manager: { id: 'manager', label: 'Manager', type: 'tier1', x: 50, y: 15, links: ['leads', 'outreach'] },
  leads: { id: 'leads', label: 'Leads Orchestrator', type: 'tier2', x: 28, y: 38, links: ['manager', 'rag', 'store'] },
  outreach: { id: 'outreach', label: 'Outreach Orchestrator', type: 'tier2', x: 72, y: 38, links: ['manager', 'copy', 'store'] },
  rag: { id: 'rag', label: 'RAG', type: 'tier3', x: 18, y: 62, links: ['leads', 'vector'] },
  store: { id: 'store', label: 'Persistence', type: 'tier3', x: 50, y: 62, links: ['leads', 'outreach', 'db'] },
  copy: { id: 'copy', label: 'Copywriter', type: 'tier3', x: 82, y: 62, links: ['outreach'] },
  streams: { id: 'streams', label: 'Redis Streams', type: 'infra', x: 30, y: 85, links: ['manager', 'leads', 'outreach'] },
  db: { id: 'db', label: 'Supabase', type: 'infra', x: 50, y: 85, links: ['store'] },
  vector: { id: 'vector', label: 'Vector DB', type: 'infra', x: 70, y: 85, links: ['rag'] },
};

const flows: Flow[] = [
  { id: 'inbound', name: 'Inbound Reply', colorVar: '--viz-a', path: ['manager', 'leads', 'rag', 'store', 'outreach', 'copy'] },
  { id: 'enrich', name: 'Enrichment', colorVar: '--viz-b', path: ['manager', 'leads', 'rag', 'store'] },
  { id: 'outbound', name: 'Outbound', colorVar: '--viz-c', path: ['manager', 'outreach', 'copy', 'store'] },
];

function getCssVarHsl(varName: string): string {
  return `hsl(var(${varName}))`;
}

function getPath(from: ArchNode, to: ArchNode) {
  const x1 = from.x;
  const y1 = from.y;
  const x2 = to.x;
  const y2 = to.y;

  const midX = (x1 + x2) / 2;
  const midY = (y1 + y2) / 2;
  const curve = Math.min(10, Math.abs(y2 - y1) * 0.18 + Math.abs(x2 - x1) * 0.06);

  return `M ${x1} ${y1} Q ${midX} ${midY - curve} ${x2} ${y2}`;
}

export default function ArchitectureVisual() {
  const [activeFlow, setActiveFlow] = useState<Flow | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);

  const flowColor = useMemo(() => {
    if (!activeFlow) return null;
    return getCssVarHsl(activeFlow.colorVar);
  }, [activeFlow]);

  useEffect(() => {
    const interval = setInterval(() => {
      if (hovered) return;
      const next = flows[Math.floor(Math.random() * flows.length)];
      setActiveFlow(next);
    }, 5500);

    return () => clearInterval(interval);
  }, [hovered]);

  const isActiveEdge = (a: string, b: string) => {
    if (!activeFlow) return false;
    for (let i = 0; i < activeFlow.path.length - 1; i++) {
      const p = activeFlow.path[i];
      const q = activeFlow.path[i + 1];
      if ((p === a && q === b) || (p === b && q === a)) return true;
    }
    return false;
  };

  const nodeStroke = (type: NodeType) => {
    if (type === 'tier1') return 'hsl(var(--viz-a) / 0.85)';
    if (type === 'tier2') return 'hsl(var(--viz-b) / 0.70)';
    if (type === 'tier3') return 'hsl(var(--viz-c) / 0.70)';
    return 'hsl(var(--muted-foreground) / 0.45)';
  };

  return (
    <div className="relative">
      <div className="absolute inset-0 bg-grid-subtle opacity-30" />
      <div className="absolute inset-0 bg-radial-soft" />
      <div className="absolute inset-y-0 left-0 w-[60%] viz-sweep opacity-0 animate-sweep" />

      <div className="relative glass-soft shadow-soft rounded-2xl border overflow-hidden">
        <div className="p-4 md:p-6 border-b border-border flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="text-xs font-mono text-muted-foreground tracking-widest">// ARCHITECTURE</div>
            <div className="text-lg font-semibold">3-tier agent orchestration (calm viz)</div>
          </div>

          <div className="flex flex-wrap gap-2">
            {flows.map((f) => {
              const selected = activeFlow?.id === f.id;
              return (
                <button
                  key={f.id}
                  type="button"
                  onClick={() => setActiveFlow(selected ? null : f)}
                  className="pointer-events-auto px-3 py-1.5 rounded-md border text-xs font-mono tracking-wider transition-colors"
                  style={{
                    borderColor: selected ? `hsl(var(${f.colorVar}) / 0.65)` : 'hsl(var(--border))',
                    backgroundColor: selected ? `hsl(var(${f.colorVar}) / 0.10)` : 'transparent',
                    color: selected ? `hsl(var(${f.colorVar}) / 0.95)` : 'hsl(var(--muted-foreground))',
                  }}
                >
                  {f.name}
                </button>
              );
            })}
          </div>
        </div>

        <div className="p-2 md:p-4">
          <svg className="w-full" viewBox="0 0 100 100" style={{ minHeight: 420 }}>
            <defs>
              <filter id="softGlow">
                <feGaussianBlur stdDeviation="1.2" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>

            {/* edges */}
            {Object.values(nodes).flatMap((n) =>
              n.links.map((t) => {
                const to = nodes[t];
                if (!to) return null;

                const active = isActiveEdge(n.id, to.id);
                const hovering = hovered === n.id || hovered === to.id;

                return (
                  <g key={`${n.id}-${to.id}`}>
                    <path
                      d={getPath(n, to)}
                      fill="none"
                      stroke={
                        active
                          ? flowColor || 'hsl(var(--viz-a) / 0.85)'
                          : hovering
                            ? 'hsl(var(--muted-foreground) / 0.55)'
                            : 'hsl(var(--muted-foreground) / 0.28)'
                      }
                      strokeWidth={active ? 0.28 : 0.12}
                      opacity={active ? 0.75 : hovering ? 0.55 : 0.35}
                      style={{ transition: 'all 400ms ease' }}
                    />

                    {active && (
                      <circle r="0.35" fill={flowColor || 'hsl(var(--viz-a))'} filter="url(#softGlow)">
                        <animateMotion dur="3.4s" repeatCount="indefinite" path={getPath(n, to)} />
                      </circle>
                    )}
                  </g>
                );
              })
            )}

            {/* nodes */}
            {Object.values(nodes).map((n) => {
              const inFlow = activeFlow?.path.includes(n.id);
              const stroke = inFlow ? (flowColor || nodeStroke(n.type)) : nodeStroke(n.type);
              const fill = inFlow ? 'hsl(var(--background))' : 'hsl(var(--card))';

              return (
                <g
                  key={n.id}
                  onMouseEnter={() => setHovered(n.id)}
                  onMouseLeave={() => setHovered(null)}
                  style={{ cursor: 'default' }}
                >
                  <circle
                    cx={n.x}
                    cy={n.y}
                    r="2.1"
                    fill={fill}
                    stroke={stroke}
                    strokeWidth="0.22"
                    opacity={inFlow ? 1 : 0.9}
                    filter={inFlow ? 'url(#softGlow)' : undefined}
                  />
                  <circle
                    cx={n.x}
                    cy={n.y}
                    r="0.65"
                    fill={stroke}
                    opacity={inFlow ? 0.9 : 0.45}
                  >
                    {inFlow && <animate attributeName="opacity" values="0.35;0.95;0.35" dur="2.8s" repeatCount="indefinite" />}
                  </circle>

                  <text
                    x={n.x}
                    y={n.y + 5}
                    textAnchor="middle"
                    fill={inFlow ? stroke : 'hsl(var(--muted-foreground) / 0.6)'}
                    fontSize="1.2"
                    fontFamily="var(--font-mono), ui-monospace, monospace"
                    style={{ transition: 'all 400ms ease' }}
                  >
                    {n.label.toUpperCase()}
                  </text>
                </g>
              );
            })}

            {/* tier labels */}
            <text x="3" y="10" fill="hsl(var(--muted-foreground) / 0.35)" fontSize="1.0" fontFamily="var(--font-mono)">
              // TIER 1
            </text>
            <text x="3" y="33" fill="hsl(var(--muted-foreground) / 0.35)" fontSize="1.0" fontFamily="var(--font-mono)">
              // TIER 2
            </text>
            <text x="3" y="57" fill="hsl(var(--muted-foreground) / 0.35)" fontSize="1.0" fontFamily="var(--font-mono)">
              // TIER 3
            </text>
            <text x="3" y="82" fill="hsl(var(--muted-foreground) / 0.35)" fontSize="1.0" fontFamily="var(--font-mono)">
              // INFRA
            </text>
          </svg>

          <div className="px-3 pb-4 pt-1 text-xs text-muted-foreground flex items-center justify-between">
            <div className="font-mono">[ hover nodes to focus edges ]</div>
            <div className="font-mono">[ click flow buttons to trace ]</div>
          </div>
        </div>
      </div>
    </div>
  );
}
