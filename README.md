<div align="center">

# Agentic System — Work In Progress

[![CI](https://github.com/BoonBoonBoonBoon/Agentic-System-Public/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/BoonBoonBoonBoon/Agentic-System-Public/actions/workflows/ci.yml)
[![coverage](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/BoonBoonBoonBoon/Agentic-System-Public/refs/heads/main/coverage-badge.json)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](requirements.txt)

</div>

## TL;DR
- Built a modular agent framework focused on orchestration and auditable Retrieval-Augmented Generation (RAG).
- Emphasis on clean seams (DI/Protocols), testability, provenance, and safe-by-default patterns.
- This repo is sanitized and portfolio-oriented: code is illustrative, not a turnkey product.

What to skim (5–7 minutes):
- `agent/operational_agents/rag_agent/rag_agent.py` — core RAG agent surface and tool wrappers.
- `agent/tools/persistence/service.py` — adapter + service pattern (Supabase or in-memory) with read-only façade.
- `agent/Infastructure/queue/interface.py` — clean queue protocol; infra primitives are test-friendly.
- `platform_monitoring/exporters.py` — event logging with redaction hooks for safety.
- `tests/test_rag_public_leads_integration.py` — how mock vs. live reads are separated.
 - `agent/operational_agents/db_write_agent/db_write_agent.py` — minimal write agent used in tests.
 - `scripts/secret_scan.py` — lightweight local scanner CI also runs.

Deeper dive: see `docs/ARCHITECTURE.md` and `docs/CODE_TOUR.md`. For a developer-oriented roadmap, see `docs/ROADMAP.md`. For orchestration vs tools, see `docs/LANGGRAPH_VS_LANGCHAIN.md`.

## Highlights
- Deterministic envelope pattern (metadata + records + provenance) for inter-agent IO.
- Read-only façades for RAG to enforce least-privilege querying.
- Pluggable adapters (in-memory / Supabase) behind a single service interface.
- Lightweight infra: queue/dispatcher/worker for local dev and demonstration.
- Test toggles for “mock vs real” flows; CI runs offline tests and secret scans only.

## Skills demonstrated
- Python, async-ish orchestration patterns, test design (pytest), dependency inversion via Protocols.
- RAG architecture, data access layering, and audit/provenance design.
- CI/CD hygiene (secret scanning, env isolation), documentation for technical storytelling.

## Architecture at a glance
See `docs/ARCHITECTURE.md` for a one-page diagram and flow notes.

## Code tour
Quick links and why they matter: `docs/CODE_TOUR.md`.

## Demo script (talk track)
- I included a short, offline demo flow and notes in `docs/DEMO.md` so I can walk reviewers through the design quickly.

## Disclaimer / Ethics
- This is a public demonstration of a private product developed by my LLC. It’s intentionally simplified and partially mocked.
- All secrets and sensitive logs have been removed; see `docs/SANITIZATION.md` for details.
- This repository is provided as a portfolio showcase under the MIT license; it is not positioned as production-ready.

## Project layout (high level)
- `agent/` — orchestrators, registries, agents, and infra.
  - `Infastructure/` — interfaces + primitives (queue, worker, engine stubs).
  - `high_level_agents/` — control layer and domain orchestrators.
  - `operational_agents/` — focused I/O (RAG agent, copywriter, db write).
  - `tools/` — deterministic clients/helpers (persistence, data coordination).
  - `utils/` — envelope utilities and optional schemas.
- `platform_monitoring/` — sanitized telemetry helpers.
- Redis (optional): see `docs/REDIS.md` for Streams topology and ops.
- `tests/` — unit + integration (real tests gated by `USE_REAL_TESTS=1`).
- `docs/` — architecture, code tour, demo, sanitization notes, portfolio one‑pager.

## How to review (suggested path)
1. Skim `docs/PORTFOLIO.md` for the narrative (problem → solution → impact).
2. Open `docs/ARCHITECTURE.md` for the diagram and flow.
3. Read `agent/tools/persistence/service.py` to see the seam design (adapters/allowlists).
4. Open `agent/operational_agents/rag_agent/rag_agent.py` for the agent shape and envelopes.
5. Check `platform_monitoring/exporters.py` for redaction before logging.

## CI & safety
- CI runs offline tests + secret scan (see `.github/workflows/ci.yml`).
- CI, coverage, and badges documentation: `docs/CI.md`.
- Real external calls are opt-in for local dev only: set `USE_REAL_TESTS=1` if you actually wire credentials.
- Sanitization details and guidance: `docs/SANITIZATION.md`.

## Repo metadata (suggestions)
Add these to the GitHub repo settings (not in code):
- Description: “Modular agent orchestration + RAG (portfolio showcase). DI, adapters, provenance, tests.”
- Topics: `agent`, `rag`, `langchain`, `langgraph`, `supabase`, `python`, `portfolio`.
- Pin links: `docs/ARCHITECTURE.md`, `docs/CODE_TOUR.md`, `agent/operational_agents/rag_agent/rag_agent.py`.

---

If you’re short on time, jump straight to `docs/PORTFOLIO.md` and the Code Tour. Thanks for reviewing!

