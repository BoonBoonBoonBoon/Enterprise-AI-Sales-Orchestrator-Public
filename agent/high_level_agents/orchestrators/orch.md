**Goal**: design a small, maintainable set of mid-level orchestrators that sit between the control plane and operational agents, letting ~12 operational agents be composed into safe, testable workflows.

**High-level pattern**
- **Orchestrator**: a named, discoverable unit that receives a `payload` and returns the canonical envelope `{metadata, records[]}` (or raises).  
- **Operational Agent (Tool)**: an injectable, well-typed callable that does one job (DB read, vector search, email send, transform, etc.). Orchestrators call these tools via a light adapter layer.  
- **Registry**: mapping name → orchestrator factory; used by `Worker` to resolve flows.  
- **Contract**: every orchestrator implements `run(payload: dict) -> dict` and emits provenance on records. Orchestrator may call tools sync or delegate async via queue.

**Types of orchestrators to implement**
(These are small, composable roles — you don’t need one orchestrator per operational agent)

- **Coordinator**:  
  - Purpose: coordinate multiple agents in sequence (fetch → transform → persist → notify).  
  - Example calls: `DataCoordinator`, `Transformer`, `AuditStore`, `Delivery`.  
  - Contract: sequential steps, stops on fatal error, emits single envelope.  
  - Retry semantics: orchestrator-level retries for transient tool failures (configurable attempts).

- **Aggregator**:  
  - Purpose: call multiple data sources in parallel and merge results into one envelope.  
  - Example calls: `SupabaseReader`, `VectorSearch`, `ExternalAPI`.  
  - Contract: consolidates records, de-duplicates by key, adds combined provenance.  
  - Failure mode: partial success allowed (with `metadata.partial=true`).

- **Enricher**:  
  - Purpose: take upstream records and enrich each via other agents (e.g., resolve company info).  
  - Example calls: `EnrichmentService`, `DataCoordinator`.  
  - Contract: returns original records with extra fields + per-record provenance.

- **Transformer**:  
  - Purpose: apply deterministic transforms / validation on records (schema, normalization).  
  - Example calls: internal functions or `ValidationAgent`.  
  - Contract: may drop/annotate invalid records; returns normalized records and validation report.

- **Router / Switch**:  
  - Purpose: choose a sub-flow based on payload content (eg. lead vs support email).  
  - Example calls: none or a light classifier, then delegates to `Coordinator` or `Delivery` orchestrators.  
  - Contract: deterministic routing, returns envelope from chosen sub-orchestrator.

- **Delivery Orchestrator**:  
  - Purpose: handle delivery gating, call the `Delivery` agent(s) and record outcome.  
  - Example calls: `DeliveryTool`, `AuditStore`, `RateLimiter`.  
  - Contract: idempotent delivery attempts, respects `allow_delivery` flag and fails safely with `DISABLED` reason.

- **Executor / Actioner**:  
  - Purpose: perform side-effects (create CRM record, send email).  
  - Example calls: `CRMWrite`, `SendEmail`.  
  - Contract: returns a success/failure envelope and a side-effect id; must be reversible via Compensation (if implemented).

- **Compensation / Saga Orchestrator**:  
  - Purpose: for flows with multiple side-effects, implement compensating actions on partial failures.  
  - Example calls: `CRMDelete`, `RevokeAccess`.  
  - Contract: rollback steps, idempotent compensators.

- **Validator**:  
  - Purpose: apply business-rule checks (fraud, policy) before heavy work.  
  - Example calls: `PolicyService`, `RiskScore`.  
  - Contract: can short-circuit flow with `metadata: {blocked: true, reason: ...}`.

- **Scheduler / Delay Orchestrator**:  
  - Purpose: schedule follow-up tasks (reminders, retries) by enqueuing jobs.  
  - Example calls: `QueueInterface.enqueue`.  
  - Contract: no heavy compute; returns run descriptor and scheduling metadata.

- **Audit / Archiver**:  
  - Purpose: finalize and persist envelopes to the `AuditStore` and to long-term storage.  
  - Example calls: `AuditStore`, `S3Adapter`.  
  - Contract: durable write; failure should trigger alerts and safe retry.

- **Monitor / Sampler**:  
  - Purpose: create sampled telemetry snapshots of envelopes for observability.  
  - Example calls: `platform_monitoring.log_event`, `PrometheusExporter`.  
  - Contract: non-blocking, best-effort telemetry writes.

**Common Orchestrator contract (recommended interface)**
- `class BaseOrchestrator:`  
  - `def __init__(self, tools: ToolContainer, config: dict = None)`: receive injected tool adapters.  
  - `def run(self, payload: dict) -> dict`: synchronous run, returns canonical envelope.  
  - `async def run_async(self, payload: dict) -> str`: optional — enqueue and return job id.  
  - `def validate_payload(self, payload) -> None | raises`: validate early.  
  - Hooks: `before_run(payload)`, `after_run(envelope)`, `on_error(exc, meta)` for logging/audit.  
  - Observability: orchestrators call `platform_monitoring.log_event(...)` at start/success/error.

**Tool injection & adapters**
- Use a `ToolContainer` / DI object to pass operational agents to orchestrators (makes testing trivial).  
- Adapter pattern: wrap third-party libs behind small adapters (`SupabaseAdapter`, `EmailAdapter`) with clear, minimal methods.  
- Example `ToolContainer` keys: `data_coordinator`, `vector_search`, `delivery`, `audit_store`, `validator`, `rate_limiter`.

**Permissions & safety**
- **Capability list**: each orchestrator declares allowed tool capabilities (read, write, send). Tools enforce capability checks.  
- **Delivery gating**: global `allow_delivery` flag in `CampaignManager` and enforcement in `Delivery Orchestrator`.  
- **Sandboxing**: orchestrators should only accept inputs validated by `Validator` to avoid accidental sensitive actions.

**Failure handling & retries**
- Classify failures: `transient` vs `permanent`.  
- Default strategy: transient retries with exponential backoff (configurable), permanent errors fail the orchestrator and result saved to audit with `metadata.error`.  
- For multi-step flows, prefer compensating actions if side-effects occurred.

**Observability & auditing**
- Emit `platform_monitoring.log_event` at: `orchestrator.start`, `orchestrator.step.*`, `orchestrator.success`, `orchestrator.error`.  
- Persist final envelope via `AuditStore` (interface + `InMemoryAuditStore` for tests).  
- Add minimal trace id propagation: `run_id` passed through calls, included in envelope metadata.

**File layout (suggested)**
- orchestrators
  - `base_orchestrator.py` (BaseOrchestrator + ToolContainer types)  
  - `coordinator.py`  
  - `aggregator.py`  
  - `enricher.py`  
  - `delivery_orchestrator.py`  
  - `scheduler.py`  
  - `compensation.py`  
  - __init__.py re-exporting classes (no shims pointing to other packages)

**Testing strategy**
- Unit tests for each orchestrator: inject `MagicMock`/`FakeTool` objects, assert:
  - `run()` returns expected envelope shape and provenance.
  - Correct tools were called with expected args.
  - Error paths produce audit record and expected requeue/ack behavior.
- Integration smoke: small test that registers `FakeOrch` in `Registry`, uses `InMemoryQueue` + `Worker`, calls `CampaignManager.ingest_event`, runs `worker.run_once`, asserts queue empty and audit recorded.

**Acceptance criteria for a minimal MVP**
- Implement `BaseOrchestrator`, `Coordinator`, and `DeliveryOrchestrator`.  
- Provide `ToolContainer` with `data_coordinator`, `delivery`, `audit_store`.  
- Add `InMemoryAuditStore` and tests that show: ingest mock email → enqueue → worker runs → audit contains envelope.  
- All flows return canonical envelope with `metadata` and `records[]` and per-record `provenance`.

**Proposed next step (I can implement)**
- Implement `BaseOrchestrator`, `Coordinator`, `DeliveryOrchestrator`, `ToolContainer`, and `InMemoryAuditStore` plus:
  - One example orchestrator `lead_sync` that uses `data_coordinator` then `enricher` then `delivery` (delivery toggled by config).  
  - Unit test exercising the full path (ingest → enqueue → worker → audit).

Do you want me to:
- Implement the minimal MVP orchestrators + tests now? (I’ll create files under orchestrators and tests), or
- Prototype just one orchestrator (`Coordinator`) and the `InMemoryAuditStore` to validate the pattern first?