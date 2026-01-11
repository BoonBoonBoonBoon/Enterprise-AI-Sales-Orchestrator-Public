# Deprecations and Removals

This document lists modules, scripts, and patterns that are deprecated or no longer in active use, along with their replacements and rationale.

Last updated: 2025-10-19

## Summary

- Deprecated data access:
  - agent/tools/supabase_tools.py → Use PersistenceService + SupabaseAdapter via ReadOnlyPersistenceFacade
  - agent/tools/data_coordinator.py → Use ReadOnlyPersistenceFacade.query() directly

- Deprecated queue abstraction (legacy):
  - agent/Infastructure/queue/adapters/redis_streams_queue.py → Use Streams worker + agent.tools.redis.client
  - agent/Infastructure/queue/factory.py → Use streams directly; no factory
  - agent/Infastructure/queue/in_memory.py, interface.py → Test-only utilities (kept for unit tests)

- Deprecated scripts:
  - scripts/redis_queue_example.py → Use agent.tools.redis.client + workers
  - scripts/start_worker.py → Use python -m agent.operational_agents.rag_agent.worker (and persistence write worker)

- Removed legacy agent:
  - agent/operational_agents/db_write_agent/db_write_agent.py (deleted)

## What replaced them

- Centralized persistence
  - PersistenceService + SupabaseAdapter for all DB access
  - ReadOnlyPersistenceFacade for RAG (least-privilege)

- Streams-first workers
  - agent/operational_agents/persistence_agent/write_worker.py (persist:tasks → persist:results)
  - agent/operational_agents/rag_agent/worker.py (rag:tasks → rag:results)
  - agent/tools/redis/{client.py,config.py} for xadd/xreadgroup/xack utilities

- Utilities and health
  - scripts/streams_health.py, scripts/streams_group_reset.py, scripts/streams_write_benchmark.py

## Why we moved away from supabase_tools and DataCoordinator

1) Security and least-privilege
   - RAG now uses a read-only facade; no write-capable keys in retrieval paths.

2) Consistency and reliability
   - One code path for queries (retries, error handling, observability) instead of bespoke calls per agent.

3) Maintainability and portability
   - Adapter layer isolates vendor SDK quirks; swapping backends or mocking is straightforward.

4) Testability
   - Facade can be mocked in unit/integration tests; agents don’t need to import vendor SDKs.

5) Architecture alignment
   - Streams-based workers decouple orchestration from IO and scale horizontally.

## Removal timeline

- supabase_tools.py, data_coordinator.py, legacy queue adapters and scripts: slated for removal after downstreams migrate. New code must not import them.

## Finding remaining references

Run a quick search for legacy symbols:

- supabase_tools, data_coordinator, DataCoordinator
- RedisStreamsQueue, build_queue, start_worker.py, redis_queue_example.py

## Cleanup checklist (actionable)

Phase A — Safe removals now (no runtime dependencies)
- [ ] Delete scripts/redis_queue_example.py (deprecated example; replaced by Streams client/benchmarks)
- [ ] Delete scripts/start_worker.py (deprecated; replaced by Streams workers in compose)
- [ ] Delete scripts/redis_health.py (superseded by scripts/streams_health.py)

Phase B — Tests and shims
- [ ] Update or remove tests that import InMemoryQueue/Worker:
  tests/test_queue_in_memory.py, tests/test_worker.py, tests/test_worker_audit.py,
  tests/test_campaign_manager_queue.py
  - Option 1: keep InMemoryQueue/interface as test-only
  - Option 2: refactor tests to use Streams or direct facades and then remove these files
- [ ] Update tests/test_agent.py: stop patching supabase_tools; use create_rag_agent(kind='memory') and mock facade

Phase C — Remove deprecated queue folder (after tests updated)
- [ ] Remove agent/Infastructure/queue/adapters/redis_streams_queue.py
- [ ] Remove agent/Infastructure/queue/factory.py
- [ ] Optionally remove agent/Infastructure/queue/in_memory.py and interface.py if tests no longer require them

Phase D — Purge legacy data access
- [ ] Remove agent/tools/supabase_tools.py
- [ ] Remove agent/tools/data_coordinator.py

Notes
- Ensure docs references are updated (done): adapters/README.md marked DEPRECATED with pointers.
- Keep docs/DEPRECATIONS.md updated as items are checked off.

## Quick commands (optional)

To search for lingering references:

```powershell
# Legacy queue and examples
git grep -n "agent\.Infastructure\.queue"
git grep -n "redis_streams_queue"
git grep -n "start_worker\.py\|redis_queue_example\.py\|redis_health\.py"

# Legacy data access
git grep -n "supabase_tools\|data_coordinator\|DataCoordinator"
```
