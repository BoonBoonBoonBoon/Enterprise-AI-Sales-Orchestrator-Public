# Demo Script (3–5 minutes)

Audience: Hiring manager / senior engineer

Goal: Show composable, testable agent orchestration with auditable RAG, offline.

Steps
1) Architecture: open `docs/ARCHITECTURE.md` (diagram). 30–45s overview.
2) Envelope: show a sample envelope structure (metadata + records + provenance).
3) Code: open `agent/tools/persistence/service.py` and `agent/operational_agents/rag_agent/rag_agent.py`; explain seams & read-only.
4) Run the offline demo script and show output envelopes.

Run the offline demo (no network)
```powershell
# Ensure virtualenv is active if you use one
python scripts/rag_demo.py --company Acme
# or
python scripts/rag_demo.py --email alice@example.com
```

Offline test command
```powershell
python -m pytest -q
```

If asked about live integrations
- Set `USE_REAL_TESTS=1` and provide Supabase credentials via environment (not committed).
- Live tests are opt-in and guarded (see `tests/test_rag_public_leads_integration.py`).

Talking points
- "I designed the seams first: Protocols for infra, Adapters for data, a Facade for least-privilege."
- "I use canonical envelopes for consistency across agents and auditability."
- "CI focuses on safety: secret scans and offline tests. Live calls are opt-in only."
