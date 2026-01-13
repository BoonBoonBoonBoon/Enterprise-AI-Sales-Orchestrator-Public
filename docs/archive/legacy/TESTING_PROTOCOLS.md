# Testing Protocols & Guidelines

## Redis Connection Management
**Date:** November 23, 2025
**Status:** Active

### Policy: Use Existing Clients
To maintain stability and avoid `redis.exceptions.ConnectionError: max number of clients reached`, the testing strategy has been updated.

**Requirement:**
- Tests **MUST** run against the currently running set of consumers ("Current Clients").
- Tests **MUST NOT** spawn new, ephemeral consumer processes ("New Clients") by default.

### Rationale
- The Redis instance has a strict connection limit.
- Spawning a duplicate set of consumers for testing doubles the connection count, causing failures.
- Testing against the live (dev) consumers ensures we are validating the actual running environment.

### Implementation
- `tests/end-to-end/test_e2e_flow.py` has been updated to skip consumer startup by default.
- Developers must ensure `python start_all_consumers.py` is running in a separate terminal before executing tests.
