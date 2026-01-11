# Incident Playbooks

This page is a practical runbook for common operational failures in the Agentic System.

## 1) Consumers Not Processing Tasks

**Symptoms**

- Stream lengths grow but no results appear
- Consumers appear "running" but no new messages processed

**Checklist**

- Verify Redis is reachable and `REDIS_URL` is correct
- Confirm tenant prefix matches (e.g. `agentic-dev:`)
- Confirm stream naming matches the hierarchical convention:
  - Manager: `{tenant}:manager:tasks` / `{tenant}:manager:results`
  - Orchestrators: `{tenant}:orchestrators:<name>:tasks` / `...:results`
  - Agents: `{tenant}:agents:<name>:tasks` / `...:results`

**Recovery**

- Restart consumers using the startup script:
  - https://github.com/BoonBoonBoonBoon/Agentic-System/blob/master/scripts/startup/restart_consumers.ps1

## 2) Persistence Writes Failing

**Symptoms**

- Persistence agent returns FK / RLS errors
- Inserts fail for `messages` due to missing `metadata`

**Checklist**

- Verify Supabase env vars are set: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_JWT_SECRET`
- Ensure correct DB role is used:
  - `agent_reader` (RAG): SELECT only
  - `agent_writer` (Persistence): CRUD
- Confirm required fields are present (notably `messages.metadata: {}`)

## 3) RAG Returns Empty Context

**Symptoms**

- Enrichment outputs are empty or generic

**Checklist**

- Confirm the tenant has data in the expected tables
- Review any `query_trace` emitted by RAG / orchestrators

## 4) Unexpected Cross-Orchestrator Messaging

**Symptoms**

- Tier 2 orchestrator attempts to publish to another orchestrator’s task stream

**Recovery**

- Ensure Tier 2 only publishes to `:agents:` streams and returns results upward.
- Cross-orchestrator coordination must route through Tier 1 Manager.

## See Also

- [API Reference](api/reference.md)
- [Updates](updates/index.md)
