# Orchestrators

This package contains small, domain-focused orchestrators that implement
high-level flows by calling operational agents. Orchestrators are thin
controllers: they validate inputs, call into the `Registry` to resolve
operational agents/tools, and return the canonical envelope (metadata + records)
from each node in the flow.

Key concepts
------------
- `BaseOrchestrator` — shared helpers and validation logic for domain
  orchestrators. Subclass this when adding a new domain flow.
- `Registry` — discovery and metadata for operational agents and tools. Use
  `Registry.get(name)` to resolve the callable or tool descriptor.
- Domain orchestrators — e.g. `LeadOrchestrator`, `DeliveryOrchestrator` —
  implement `run(...)` to perform domain-specific work.

Where this lives
-----------------
Package: `agent.high_level_agents.orchestrators`

Exports
-------
The package exposes the primary domain orchestrators and helpers:

- `LeadOrchestrator`
- `DeliveryOrchestrator`
- `BaseOrchestrator`
- `Registry`

Quick usage example
-------------------
This example shows the typical pattern inside a worker or a controller:

```python
from agent.high_level_agents.orchestrators import LeadOrchestrator, Registry

# Resolve orchestrator and run a flow
registry = Registry()
registry.register("lead_orchestrator", LeadOrchestrator)

orch_cls = registry.get("lead_orchestrator")
orch = orch_cls()
envelope = orch.run(payload={"lead_query": {"name": "Acme"}})
assert isinstance(envelope, dict)  # envelope = {"metadata":..., "records": [...]}
```

Adding a new orchestrator
-------------------------
1. Create a new module under `agent/high_level_agents/orchestrators`, e.g.
   `my_orchestrator.py`.
2. Subclass `BaseOrchestrator` and implement the `run(self, payload)` method.
3. Register the orchestrator in the `Registry` for discovery in tests or
   at runtime.

Testing
-------
- Unit tests: mock the `Registry` entries and test the orchestrator `run`
  method for happy-path and failure cases.
- Integration: run the `orchestration_engine` with an in-memory `Dispatcher`
  and mocked operational agents.

Run tests locally (PowerShell):

```powershell
$env:USE_REAL_TESTS = '0'; python -m unittest discover -v tests
```

Recommended next steps / TODOs
-----------------------------
- Wire `CampaignManager` to enqueue orchestrator runs instead of calling them
  synchronously.
- Add an `InMemoryQueue` and a lightweight `Worker` to consume jobs for local
  development; later replace with a Redis/Celery queue for production.
- Add example orchestrator implementations and unit tests that assert the
  canonical envelope contract (metadata + records + per-record provenance).

Notes
-----
- Orchestrators should not directly perform heavy data access — use
  operational agents (registered in `Registry`) for DB / vector / LLM calls so
  that provenance and the canonical envelope contract are preserved.
