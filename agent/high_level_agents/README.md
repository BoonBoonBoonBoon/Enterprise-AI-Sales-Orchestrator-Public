High-level agents (decentralized architecture)

Overview
--------
The high-level agents package contains small, focused components that orchestrate
workflows by delegating to operational agents (found in `agent/operational_agents`).
We favor decentralization: the `CampaignManager` is thin and policy-focused;
domain-specific `Orchestrators` implement flows; an `OrchestrationEngine` runs
graphs; a `Dispatcher` enforces per-agent concurrency and quotas; and a
`Scheduler` handles triggers.

Key components
--------------
- control_layer/
	- `campaign_manager.py`: thin director that receives triggers, enqueues jobs,
		applies policy (feature flags, allow_delivery), and records run metadata.
	- `scheduler.py`: simple in-memory scheduler for development; replace in prod.
- orchestrators/
	- domain orchestrators (e.g., `LeadOrchestrator`, `DeliveryOrchestrator`) that
		subclass `BaseOrchestrator` and call operational agents via the `Registry`.
- orchestration_engine/
	- `runner.py`: workflow runtime that executes node graphs, enforces retries,
		and returns canonical envelopes.
- dispatcher/
	- `dispatcher.py`: enforces per-agent concurrency limits and dispatches calls
		to operational agents. Replace with an external queue for production.
- orchestration_agents/
	- `base_orchestrator.py`, `registry.py`, and plugin helpers. The `Registry`
		provides discovery and metadata for operational agents.

How components interact (simplified)
-----------------------------------
1. `CampaignManager` receives a trigger and enqueues a job (non-blocking).
2. Worker picks up the job and calls `OrchestrationEngine` to execute the flow.
3. `OrchestrationEngine` resolves node tools via `Registry.get(name)` and uses
	 `Dispatcher.submit` to call the operational agent (respecting concurrency).
4. Each operational agent returns a canonical envelope (metadata + records).
5. `OrchestrationEngine` validates envelopes at node boundaries and emits
	 monitoring events to `platform_monitoring`.
6. Final envelope is persisted for audit and optionally delivered by the
	 `Delivery` operational agent (gated by `CampaignManager`).

Why decentralized
------------------
- Avoids a single monolithic controller; improves ownership and testing.
- Enables per-agent throttling and cost controls (e.g., LLM-heavy agents).
- Makes it easier to scale parts of the system independently.

Extending the system
---------------------
1. Add a new operational agent under `agent/operational_agents` and register it
	 in the `Registry` with a capability description.
2. If domain logic is required, add a small orchestrator under
	 `agent/high_level_agents/orchestrators` that subclasses `BaseOrchestrator`.
3. Update flows in `orchestration_engine` or register new flows in your
	 orchestration definitions.

Testing
-------
- Unit test domain orchestrators by mocking `Registry` entries for operational
	agents.
- Integration test the runner with an in-memory dispatcher and mocked agents.

Notes
-----
- This package intentionally keeps high-level code separate from operational
	agents to reduce coupling. Replace in-memory components with production
	equivalents (Redis queue, Prometheus, tracing) when deploying.

