Bottom → Top system flow (concise)

## 1.Operational agents (bottom)

Individual workers/tools (CopyAgent, DataCoordinator/SupabaseTool, QdrantTool, ReplyClassifier, DeliveryTool, etc.).
Input: tool-specific payload (or canonical envelope). Output: canonical envelope {metadata, records[], provenance}.
Responsibilities: deterministic data access, prompt execution, external side-effects (delivery gated).

## 2.Dispatcher / WorkerPool

Receives a node call, enforces per-agent concurrency/quotas/health, and invokes the operational agent.
Returns the agent’s envelope to the caller.
Acts as the single throttling/queueing point for costly agents.

## 3.Orchestration Engine (runner)

Executes workflow graphs (nodes/edges).
For each node: resolve tool via Registry → call Dispatcher.submit(tool, payload) → validate returned envelope → emit monitoring events (node_start/node_end/error).
Handles retries, timeouts, parallel nodes, and node-level policies.

## 4.Domain Orchestrators (BaseOrchestrator subclasses)

Encapsulate domain flow logic (LeadOrchestrator, DeliveryOrchestrator, ReplyOrchestrator).
Build initial context, prefer fast-path if an envelope with records is provided, call the Orchestration Engine to execute flow, post-process results.
Return final canonical envelope.

## 5.Worker / Queue (async boundary)

Job pulled from the queue (populated by CampaignManager) and executed by a worker process that runs the Domain Orchestrator / Orchestration Engine.
Enables scaling and crash isolation.

## 6.Campaign Manager / Control Layer (top)

Thin policy director: accepts triggers (API, schedule, events), selects orchestrator/flow, creates run_id, enqueues a job, applies campaign-level policy (feature flags, allow_delivery).
Receives final envelope for audit and decides delivery (honors gating).

## 7.External systems (topmost)

Schedulers, webhooks, UI, analytics dashboards feed triggers into CampaignManager and consume monitoring/audit data.
PlatformMonitoring collects events/metrics emitted at each layer for dashboards/alerts.

## Cross-cutting (applies at all levels)

Registry: single source-of-truth for agent discovery, metadata, health and capabilities.
Canonical envelope contract enforced at boundaries to prevent duplicate queries and ensure provenance.
Audit store (Supabase): persist run metadata, node traces, and final envelopes for replay and reporting.
Delivery gating and security: action-producing agents require explicit enablement and allow-lists.