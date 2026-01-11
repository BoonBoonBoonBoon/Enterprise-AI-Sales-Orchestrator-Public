# Agent Tools — Overview

Shared low-level helpers used by operational agents (DB clients, storage helpers, telemetry). Keep tools small and stable.

Contract
- Purpose: provide stable helper APIs (e.g., `SupabaseClient`) that agents import and reuse.
- Keep side effects minimal and avoid long-running operations during import.

How to use
- Import directly: `from agent.tools import SupabaseClient` (re-exported via `agent/tools/__init__.py`).
- Discoverable: `agent.tools.registry.discover_local_tools()` will find modules exposing `TOOL` or `create_tool()`.

Current tools
- `supabase_tools.py` — Supabase client wrapper and record formatting helpers.

Security
- Tools may access secrets (SUPABASE_URL, SUPABASE_KEY). Keep `.env` out of source control.

TODO (external storage / pointer)
- For large or sensitive raw rows we should NOT inline full raw_row in every envelope by default.
- Implement an object-store backing (S3 / Azure Blob / GCS) to snapshot raw rows and return a signed URL or pointer in the provenance when requested.

Provenance helpers (summary)
- Minimal provenance (default): `{source, row_id, row_hash, retrieved_at}`.
- Include full raw row only when requested with `include_raw=True` or `--include-raw`.

