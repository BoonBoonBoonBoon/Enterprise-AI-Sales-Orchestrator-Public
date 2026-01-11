"""
Redis Stream Registry - Canonical Stream Definitions

This module provides the single source of truth for all Redis streams in the system.
It enforces consistent naming, defines upstream/downstream relationships, and provides
type-safe stream access.

Architecture Pattern: Hierarchical Three-Tier with Clear Data Flow
- Tier 1 (Manager): Strategic decision-making
- Tier 2 (Orchestrators): Business logic coordination
- Tier 3 (Agents): Specialized execution

Data Flow Direction:
- Downstream: Manager → Orchestrator → Agent (task delegation)
- Upstream: Agent → Orchestrator → Manager (result propagation)
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Literal
from enum import Enum


class StreamType(Enum):
    """Types of streams in the system"""
    TASKS = "tasks"          # Input stream for tasks
    RESULTS = "results"      # Output stream for results
    EVENTS = "events"        # Event notifications
    DLQ = "dlq"             # Dead letter queue for failed messages
    HEALTH = "health"        # Health check heartbeats
    AUDIT = "audit"          # Audit trail
    METRICS = "metrics"      # Performance metrics


class Tier(Enum):
    """System tiers"""
    MANAGER = "manager"               # Tier 1: Strategic
    ORCHESTRATOR = "orchestrators"    # Tier 2: Business logic  
    AGENT = "agents"                  # Tier 3: Operational
    SYSTEM = "system"                 # System-wide streams


@dataclass
class StreamDefinition:
    """Definition of a Redis stream with metadata"""
    key_pattern: str                    # Stream key pattern (with {tenant} placeholder)
    tier: Tier                          # Which tier owns this stream
    component: str                      # Component name (e.g., "leads", "rag")
    stream_type: StreamType             # Type of stream
    consumer_group: Optional[str]       # Consumer group name
    max_len: int                        # Maximum stream length (MAXLEN ~)
    retention_hours: int                # How long to keep messages
    description: str                    # Human-readable description
    upstream: List[str] = None          # Which streams feed into this (upstream sources)
    downstream: List[str] = None        # Which streams this feeds (downstream targets)
    
    def __post_init__(self):
        if self.upstream is None:
            self.upstream = []
        if self.downstream is None:
            self.downstream = []
    
    def get_key(self, tenant_id: str) -> str:
        """Get the actual stream key for a tenant"""
        return self.key_pattern.format(tenant=tenant_id)
    
    def get_full_name(self) -> str:
        """Get human-readable full name"""
        return f"{self.tier.value}:{self.component}:{self.stream_type.value}"


class StreamRegistry:
    """
    Central registry of all Redis streams in the system.
    
    This class provides:
    1. Consistent stream naming across all components
    2. Stream metadata and configuration
    3. Upstream/downstream relationship mapping
    4. Type-safe stream access
    5. Multi-tenant stream key generation
    """
    
    def __init__(self):
        self._streams: Dict[str, StreamDefinition] = {}
        self._register_all_streams()
    
    def _register_all_streams(self):
        """Register all streams in the system"""
        
        # ==================== TIER 1: MANAGER ====================
        
        self.register(StreamDefinition(
            key_pattern="{tenant}:manager:tasks",
            tier=Tier.MANAGER,
            component="manager",
            stream_type=StreamType.TASKS,
            consumer_group="manager-workers",
            max_len=10000,
            retention_hours=48,
            description="Incoming requests from external systems (API, webhooks, etc.)",
            upstream=[],  # Entry point - no upstream
            downstream=[
                "{tenant}:orchestrators:leads:tasks",
                "{tenant}:orchestrators:outbound:tasks"
            ]
        ))
        
        self.register(StreamDefinition(
            key_pattern="{tenant}:manager:results",
            tier=Tier.MANAGER,
            component="manager",
            stream_type=StreamType.RESULTS,
            consumer_group=None,  # No consumer group - read directly by API
            max_len=10000,
            retention_hours=48,
            description="Final results returned to external systems",
            upstream=[
                "{tenant}:orchestrators:leads:results",
                "{tenant}:orchestrators:outbound:results"
            ],
            downstream=[]  # Exit point - no downstream
        ))
        
        # ==================== TIER 2: ORCHESTRATORS ====================
        
        # Leads Orchestrator
        self.register(StreamDefinition(
            key_pattern="{tenant}:orchestrators:leads:tasks",
            tier=Tier.ORCHESTRATOR,
            component="leads",
            stream_type=StreamType.TASKS,
            consumer_group="leads-workers",
            max_len=5000,
            retention_hours=24,
            description="Lead discovery and management workflows delegated from Manager",
            upstream=["{tenant}:manager:tasks"],
            downstream=[
                "{tenant}:agents:rag:tasks",
                "{tenant}:agents:persistence:tasks"
            ]
        ))
        
        self.register(StreamDefinition(
            key_pattern="{tenant}:orchestrators:leads:results",
            tier=Tier.ORCHESTRATOR,
            component="leads",
            stream_type=StreamType.RESULTS,
            consumer_group=None,
            max_len=5000,
            retention_hours=24,
            description="Lead workflow results sent back to Manager",
            upstream=[
                "{tenant}:agents:rag:results",
                "{tenant}:agents:persistence:results"
            ],
            downstream=["{tenant}:manager:results"]
        ))
        
        # Outbound Orchestrator (Outreach Campaigns)
        self.register(StreamDefinition(
            key_pattern="{tenant}:orchestrators:outbound:tasks",
            tier=Tier.ORCHESTRATOR,
            component="outbound",
            stream_type=StreamType.TASKS,
            consumer_group="outbound-workers",
            max_len=5000,
            retention_hours=24,
            description="Outbound campaign workflows delegated from Manager",
            upstream=["{tenant}:manager:tasks"],
            downstream=[
                "{tenant}:agents:copywriter:tasks",
                "{tenant}:agents:booking:tasks",
                "{tenant}:agents:sequencing:tasks"
            ]
        ))
        
        self.register(StreamDefinition(
            key_pattern="{tenant}:orchestrators:outbound:results",
            tier=Tier.ORCHESTRATOR,
            component="outbound",
            stream_type=StreamType.RESULTS,
            consumer_group=None,
            max_len=5000,
            retention_hours=24,
            description="Outbound workflow results sent back to Manager",
            upstream=[
                "{tenant}:agents:copywriter:results",
                "{tenant}:agents:booking:results",
                "{tenant}:agents:sequencing:results"
            ],
            downstream=["{tenant}:manager:results"]
        ))
        
        # ==================== TIER 3: AGENTS ====================
        
        # RAG Agent (Research & Enrichment)
        self.register(StreamDefinition(
            key_pattern="{tenant}:agents:rag:tasks",
            tier=Tier.AGENT,
            component="rag",
            stream_type=StreamType.TASKS,
            consumer_group="rag-workers",
            max_len=20000,
            retention_hours=12,
            description="Data enrichment requests (vector search, external APIs)",
            upstream=["{tenant}:orchestrators:leads:tasks"],
            downstream=["{tenant}:orchestrators:leads:results"]
        ))
        
        self.register(StreamDefinition(
            key_pattern="{tenant}:agents:rag:results",
            tier=Tier.AGENT,
            component="rag",
            stream_type=StreamType.RESULTS,
            consumer_group=None,
            max_len=20000,
            retention_hours=12,
            description="Enriched data results",
            upstream=[],
            downstream=["{tenant}:orchestrators:leads:results"]
        ))
        
        # Persistence Agent (Database Operations)
        self.register(StreamDefinition(
            key_pattern="{tenant}:agents:persistence:tasks",
            tier=Tier.AGENT,
            component="persistence",
            stream_type=StreamType.TASKS,
            consumer_group="persistence-workers",
            max_len=50000,
            retention_hours=6,
            description="Bulk database write operations",
            upstream=["{tenant}:orchestrators:leads:tasks"],
            downstream=["{tenant}:orchestrators:leads:results"]
        ))
        
        self.register(StreamDefinition(
            key_pattern="{tenant}:agents:persistence:results",
            tier=Tier.AGENT,
            component="persistence",
            stream_type=StreamType.RESULTS,
            consumer_group=None,
            max_len=10000,
            retention_hours=6,
            description="Database operation confirmations",
            upstream=[],
            downstream=["{tenant}:orchestrators:leads:results"]
        ))
        
        # Copywriter Agent (Content Generation)
        self.register(StreamDefinition(
            key_pattern="{tenant}:agents:copywriter:tasks",
            tier=Tier.AGENT,
            component="copywriter",
            stream_type=StreamType.TASKS,
            consumer_group="copywriter-workers",
            max_len=5000,
            retention_hours=24,
            description="Email and content generation requests",
            upstream=["{tenant}:orchestrators:outbound:tasks"],
            downstream=["{tenant}:orchestrators:outbound:results"]
        ))
        
        self.register(StreamDefinition(
            key_pattern="{tenant}:agents:copywriter:results",
            tier=Tier.AGENT,
            component="copywriter",
            stream_type=StreamType.RESULTS,
            consumer_group=None,
            max_len=5000,
            retention_hours=24,
            description="Generated content results",
            upstream=[],
            downstream=["{tenant}:orchestrators:outbound:results"]
        ))
        
        # Booking Agent (Calendar Management)
        self.register(StreamDefinition(
            key_pattern="{tenant}:agents:booking:tasks",
            tier=Tier.AGENT,
            component="booking",
            stream_type=StreamType.TASKS,
            consumer_group="booking-workers",
            max_len=3000,
            retention_hours=48,
            description="Meeting scheduling and calendar management",
            upstream=["{tenant}:orchestrators:outbound:tasks"],
            downstream=["{tenant}:orchestrators:outbound:results"]
        ))
        
        self.register(StreamDefinition(
            key_pattern="{tenant}:agents:booking:results",
            tier=Tier.AGENT,
            component="booking",
            stream_type=StreamType.RESULTS,
            consumer_group=None,
            max_len=3000,
            retention_hours=48,
            description="Booking confirmations and calendar events",
            upstream=[],
            downstream=["{tenant}:orchestrators:outbound:results"]
        ))
        
        # Sequencing Agent (Send Timing Optimization)
        self.register(StreamDefinition(
            key_pattern="{tenant}:agents:sequencing:tasks",
            tier=Tier.AGENT,
            component="sequencing",
            stream_type=StreamType.TASKS,
            consumer_group="sequencing-workers",
            max_len=5000,
            retention_hours=24,
            description="ML-based send time optimization",
            upstream=["{tenant}:orchestrators:outbound:tasks"],
            downstream=["{tenant}:orchestrators:outbound:results"]
        ))
        
        self.register(StreamDefinition(
            key_pattern="{tenant}:agents:sequencing:results",
            tier=Tier.AGENT,
            component="sequencing",
            stream_type=StreamType.RESULTS,
            consumer_group=None,
            max_len=5000,
            retention_hours=24,
            description="Optimized send schedules",
            upstream=[],
            downstream=["{tenant}:orchestrators:outbound:results"]
        ))
        
        # ==================== SYSTEM STREAMS ====================
        
        # Dead Letter Queue (DLQ)
        self.register(StreamDefinition(
            key_pattern="{tenant}:system:dlq",
            tier=Tier.SYSTEM,
            component="dlq",
            stream_type=StreamType.DLQ,
            consumer_group="dlq-handlers",
            max_len=100000,
            retention_hours=168,  # 7 days
            description="Failed messages from all components for manual inspection and replay",
            upstream=[],
            downstream=[]
        ))
        
        # System Events
        self.register(StreamDefinition(
            key_pattern="{tenant}:system:events",
            tier=Tier.SYSTEM,
            component="events",
            stream_type=StreamType.EVENTS,
            consumer_group="event-processors",
            max_len=50000,
            retention_hours=72,
            description="System-wide events (errors, warnings, state changes)",
            upstream=[],
            downstream=[]
        ))
        
        # Health Monitoring
        self.register(StreamDefinition(
            key_pattern="{tenant}:system:health",
            tier=Tier.SYSTEM,
            component="health",
            stream_type=StreamType.HEALTH,
            consumer_group="health-monitors",
            max_len=10000,
            retention_hours=24,
            description="Health check heartbeats from all components",
            upstream=[],
            downstream=[]
        ))
        
        # Audit Trail
        self.register(StreamDefinition(
            key_pattern="{tenant}:system:audit",
            tier=Tier.SYSTEM,
            component="audit",
            stream_type=StreamType.AUDIT,
            consumer_group="audit-processors",
            max_len=100000,
            retention_hours=720,  # 30 days
            description="Audit trail for compliance and debugging",
            upstream=[],
            downstream=[]
        ))
        
        # Metrics
        self.register(StreamDefinition(
            key_pattern="{tenant}:system:metrics",
            tier=Tier.SYSTEM,
            component="metrics",
            stream_type=StreamType.METRICS,
            consumer_group="metrics-collectors",
            max_len=50000,
            retention_hours=48,
            description="Performance metrics and statistics",
            upstream=[],
            downstream=[]
        ))
    
    def register(self, stream_def: StreamDefinition):
        """Register a stream definition"""
        key = stream_def.get_full_name()
        self._streams[key] = stream_def
    
    def get(self, tier: Tier, component: str, stream_type: StreamType) -> StreamDefinition:
        """Get a stream definition"""
        key = f"{tier.value}:{component}:{stream_type.value}"
        if key not in self._streams:
            raise KeyError(f"Stream not found: {key}")
        return self._streams[key]
    
    def get_stream_key(self, tier: Tier, component: str, stream_type: StreamType, tenant_id: str) -> str:
        """Get the actual Redis stream key for a tenant"""
        stream_def = self.get(tier, component, stream_type)
        return stream_def.get_key(tenant_id)

    # -----------------
    # Compatibility API
    # -----------------

    def get_stream(self, component: str, stream_type: StreamType, tier: Tier = Tier.AGENT) -> StreamDefinition:
        """Compatibility wrapper for older tests.

        Historically some tests called get_stream(component, stream_type) and assumed Tier.AGENT.
        """
        return self.get(tier, component, stream_type)
    
    def get_all_streams(self, tenant_id: str) -> Dict[str, str]:
        """Get all stream keys for a tenant"""
        return {
            name: stream_def.get_key(tenant_id)
            for name, stream_def in self._streams.items()
        }
    
    def get_tier_streams(self, tier: Tier, tenant_id: str) -> Dict[str, str]:
        """Get all streams for a specific tier"""
        return {
            name: stream_def.get_key(tenant_id)
            for name, stream_def in self._streams.items()
            if stream_def.tier == tier
        }
    
    def get_downstream_streams(self, tier: Tier, component: str, stream_type: StreamType, tenant_id: str) -> List[str]:
        """Get all downstream streams (where this stream sends data)"""
        stream_def = self.get(tier, component, stream_type)
        return [key.format(tenant=tenant_id) for key in stream_def.downstream]
    
    def get_upstream_streams(self, tier: Tier, component: str, stream_type: StreamType, tenant_id: str) -> List[str]:
        """Get all upstream streams (where this stream receives data from)"""
        stream_def = self.get(tier, component, stream_type)
        return [key.format(tenant=tenant_id) for key in stream_def.upstream]
    
    def get_data_flow_graph(self, tenant_id: str) -> Dict[str, List[str]]:
        """
        Get the complete data flow graph showing all upstream/downstream relationships.
        Returns: {stream_key: [downstream_keys]}
        """
        graph = {}
        for stream_def in self._streams.values():
            stream_key = stream_def.get_key(tenant_id)
            downstream_keys = [key.format(tenant=tenant_id) for key in stream_def.downstream]
            graph[stream_key] = downstream_keys
        return graph
    
    def visualize_data_flow(self, tenant_id: str) -> str:
        """Generate ASCII visualization of data flow"""
        lines = []
        lines.append("=" * 80)
        lines.append(f"  DATA FLOW DIAGRAM - Tenant: {tenant_id}")
        lines.append("=" * 80)
        lines.append("")
        
        # Tier 1
        lines.append("TIER 1: MANAGER (Strategic)")
        lines.append("-" * 80)
        manager_streams = [(name, s) for name, s in self._streams.items() if s.tier == Tier.MANAGER]
        for name, stream in manager_streams:
            key = stream.get_key(tenant_id)
            lines.append(f"  {key}")
            if stream.downstream:
                for ds in stream.downstream:
                    lines.append(f"    └─> {ds.format(tenant=tenant_id)}")
        lines.append("")
        
        # Tier 2
        lines.append("TIER 2: ORCHESTRATORS (Business Logic)")
        lines.append("-" * 80)
        orch_streams = [(name, s) for name, s in self._streams.items() if s.tier == Tier.ORCHESTRATOR]
        for name, stream in orch_streams:
            key = stream.get_key(tenant_id)
            lines.append(f"  {key}")
            if stream.downstream:
                for ds in stream.downstream:
                    lines.append(f"    └─> {ds.format(tenant=tenant_id)}")
        lines.append("")
        
        # Tier 3
        lines.append("TIER 3: AGENTS (Operational)")
        lines.append("-" * 80)
        agent_streams = [(name, s) for name, s in self._streams.items() if s.tier == Tier.AGENT]
        # Group by component
        components = {}
        for name, stream in agent_streams:
            if stream.component not in components:
                components[stream.component] = []
            components[stream.component].append((name, stream))
        
        for component, streams in sorted(components.items()):
            lines.append(f"  {component.upper()} Agent:")
            for name, stream in streams:
                key = stream.get_key(tenant_id)
                lines.append(f"    {key}")
                if stream.downstream:
                    for ds in stream.downstream:
                        lines.append(f"      └─> {ds.format(tenant=tenant_id)}")
            lines.append("")
        
        # System streams
        lines.append("SYSTEM STREAMS (Monitoring & Observability)")
        lines.append("-" * 80)
        system_streams = [(name, s) for name, s in self._streams.items() if s.tier == Tier.SYSTEM]
        for name, stream in system_streams:
            key = stream.get_key(tenant_id)
            lines.append(f"  {key} - {stream.description}")
        lines.append("")
        
        return "\n".join(lines)


# Global registry instance
_registry: Optional[StreamRegistry] = None


def get_registry() -> StreamRegistry:
    """Get the global stream registry instance"""
    global _registry
    if _registry is None:
        _registry = StreamRegistry()
    return _registry


def get_stream_key(tier: Tier, component: str, stream_type: StreamType, tenant_id: str) -> str:
    """Convenience function to get a stream key"""
    return get_registry().get_stream_key(tier, component, stream_type, tenant_id)


__all__ = [
    "StreamRegistry",
    "StreamDefinition",
    "StreamType",
    "Tier",
    "get_registry",
    "get_stream_key",
]
