# Manager routing configuration

This folder contains config for the Tier 1 Manager's deterministic routing.

- File: `routing.yaml`
  - `intents`: Maps a recognized intent to a list of Tier 2 orchestrators.
  - `tenants`: Optional per-tenant overrides to the default intent mappings.
  - `default_fallback_orchestrator`: Orchestrator to use when no mapping exists for an intent or when classification fails. Defaults to `control`.

## Optional LLM fallback

You can enable an LLM-backed intent classifier as a secondary signal after rules-based classification.

Environment variables:

- `OPENAI_API_KEY`: If set, LLM classification is **auto-enabled** by default and used as a secondary signal.
- `MANAGER_LLM_ENABLED`: Optional kill-switch. If set to `0`, `false`, or `no`, LLM is disabled even when an API key is present.
- `MANAGER_LLM_MODEL`: Optional; the OpenAI model name to use (default: `gpt-4o-mini`).

Notes:
- If no API key is configured or an error occurs, the system falls back to deterministic routing.
- Decisions are tagged via `used_fallback` in `ManagerDecision` to indicate whether the default fallback orchestrator was used.
