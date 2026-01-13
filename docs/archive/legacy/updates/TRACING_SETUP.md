# Tracing Setup

This system supports tracing in multiple layers (consumer → orchestrator → agent).

## Current State

- Tracing details are being consolidated into the MkDocs site.
- For operational deployment-level observability guidance, see the repository deployment docs:
  - https://github.com/BoonBoonBoonBoon/Agentic-System/blob/master/deployment/DEV_OBSERVABILITY_GUIDE.md
  - https://github.com/BoonBoonBoonBoon/Agentic-System/blob/master/deployment/OBSERVABILITY.md

## In-Repo Pointers

- Core observability utilities live under `core/observability/`.

## Troubleshooting

- If traces are missing, verify any required env vars/config are set and that the relevant instrumentation is enabled for your runtime.
