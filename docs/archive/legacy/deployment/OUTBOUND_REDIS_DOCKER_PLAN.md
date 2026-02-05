```markdown
# Outbound Orchestrator + Tier-3 Agents: Redis + Docker Setup Plan

Date: 2025-12-12

Goal: Run a complete outbound flow in Docker using Redis Streams:
- Tier 2 orchestrator listens on `{tenant}:orchestrators:outbound:tasks` and publishes to `{tenant}:orchestrators:outbound:results`.
- Tier 3 agents consume from the already-existing agent streams:
  - Booking (scheduler): `{tenant}:agents:booking:tasks` → `{tenant}:agents:booking:results`
  - Copywriter: `{tenant}:agents:copywriter:tasks` → `{tenant}:agents:copywriter:results`
  - Sequencing (channel sequencer): `{tenant}:agents:sequencing:tasks` → `{tenant}:agents:sequencing:results`

## Model selection (best outcomes)

Use different models for different phases.

- **GPT-5.2 (Preview)**: best for architecture decisions, stream contract decisions, multi-file coordination, and tricky debugging.
- **GPT-5.1 Codex Max**: best for implementation throughput (editing files, adding consumers/services, writing tests, fixing build/test errors).
- **Claude Sonnet 4.5**: strong fast generalist; good for day-to-day coding + docs when you want speed.
- **Claude Opus 4.5**: strong for deep reasoning + long-form synthesis (design reviews, edge-case analysis), but usually slower/costlier.

Rule of thumb:
- Design/coordination steps → GPT-5.2 (Preview) (or Opus 4.5 for deeper review).
- Pure implementation steps → Codex Max (or Sonnet 4.5 if you want a fast generalist).

## Execution plan

### 1) Lock stream naming + contracts (highest priority)
**Outcome:** One source of truth for stream names across: consumers, delegation tools, tests, scripts, and Docker.

Actions:
- Decide the canonical Tier-2 outbound stream name:
  - Recommended: keep **outbound** (since it’s already used in code).
  - Ensure Redis keys exist: `{tenant}:orchestrators:outbound:tasks/results`.
- Ensure Tier-3 stream names match what’s already in Redis:
  - Scheduler maps to **booking** streams.
  - Channel sequencer maps to **sequencing** streams.
- Update any remaining references to old names (`outreach`, `channel_sequencer_agent`, `scheduler_agent`) in:
  - manager delegation tools
  - tier_2 consumers
  - tests
  - scripts that create/migrate streams

**Model:** GPT-5.2 (Preview)

### 2) Ensure Tier-2 outbound orchestrator consumer exists and matches leads pattern
**Outcome:** A consumer under `tiers/tier_2/<outbound-orchestrator>/consumer.py` that behaves like Leads’ consumer:
- reads `{tenant}:orchestrators:outbound:tasks`
- writes `{tenant}:orchestrators:outbound:results`
- parses typed envelopes and emits result/error envelopes

Actions:
- Reuse the existing outreach orchestrator implementation if it already provides the desired outbound orchestration logic.
- Confirm `ManagerAgent` routes outbound tasks to `{tenant}:orchestrators:outbound:tasks`.

**Model:** Codex Max

### 3) Make Tier-3 consumers strictly use existing agent streams
**Outcome:** Docker + local runs attach to the same streams you already see in RedisInsight.

Actions:
- Booking worker (SchedulerAgent consumer):
  - Task stream: `{tenant}:agents:booking:tasks`
  - Result stream: `{tenant}:agents:booking:results`
- Sequencing worker (ChannelSequencerAgent consumer):
  - Task stream: `{tenant}:agents:sequencing:tasks`
  - Result stream: `{tenant}:agents:sequencing:results`
- Copywriter worker already uses `{tenant}:agents:copywriter:*`.

**Model:** Codex Max

### 4) Docker: add missing services in deployment compose
**Outcome:** `docker compose` can run manager + orchestrators + all relevant agents.

Actions:
- Add services to `deployment/docker-compose.yml` for:
  - booking (scheduler consumer)
  - sequencing (channel sequencer consumer)
- Ensure services set env vars:
  - `TENANT_ID` (e.g. `agentic-dev`)
  - `REDIS_URL`
  - any LLM keys needed by copywriter (optional fallback exists)

**Model:** Codex Max

### 5) Tests: add minimal smoke coverage for new consumers
**Outcome:** CI/pytest catches import and stream-name regressions.

Actions:
- Smoke tests:
  - import consumers/harnesses
  - verify task/result stream names are correct
  - verify minimal handler path returns a dict with `status`
- Integration tests:
  - manager routes to outbound stream
  - outbound orchestrator delegates to booking/copywriter/sequencing streams

**Model:** Codex Max (implementation), GPT-5.2 (if diagnosing tricky failures)

### 6) Optional: Deduplication stream cleanup
**Outcome:** No dangling streams in registry for agents that don’t exist.

Actions:
- If DeduplicationAgent is not being built now:
  - remove it from registry and docker compose
  - or leave streams defined but document it as "not implemented"

**Model:** GPT-5.2 (Preview)

### 7) End-to-end verification (local + Docker)
**Outcome:** A single task placed on `{tenant}:manager:tasks` produces results through outbound orchestrator and Tier-3 agents.

Actions:
- Start Docker services.
- Publish a minimal typed envelope task for outbound.
- Confirm results appear on:
  - `{tenant}:orchestrators:outbound:results`
  - and delegated agent result streams.

#### Step 7 commands (Windows PowerShell)

Prereqs:
- Create `deployment/.env` (it is gitignored). At minimum set:
  - `TENANT_ID=agentic-dev`
  - `REDIS_URL_DOCKER=redis://redis:6379/0`
  - `SUPABASE_URL=...` and `SUPABASE_KEY=...` (if running persistence)
  - `OPENAI_API_KEY=...` (if running copywriter)

Recommended local verification loop (matches the dev loop section):
- `& ".\.venv\Scripts\python.exe" -m pytest tests\smoke -v`
- `& ".\.venv\Scripts\python.exe" -m pytest tests\integration -v`

Compose validation (safe — does NOT print interpolated secrets):
- `docker compose -f deployment\docker-compose.yml config --no-interpolate`

Bring up the Docker stack:
- `docker compose -f deployment\docker-compose.yml --profile local up -d --build`

Then publish one Manager task and verify outbound + Tier-3 streams:
- Run the E2E script against Redis on localhost (Docker publishes Redis port 6379):
  - `& ".\.venv\Scripts\python.exe" tests\end-to-end\test_e2e_flow.py`

System-wide stream wiring audit (verifies canonical stream keys + consumer groups):
- ` $env:TENANT_ID='agentic-dev'; $env:REDIS_URL='redis://localhost:6379/0'; & ".\.venv\Scripts\python.exe" scripts\health_check.py --pretty `

Expected:
- Redis Streams should increment / produce results on:
  - `agentic-dev:orchestrators:outbound:results`
  - `agentic-dev:agents:copywriter:results`
  - `agentic-dev:agents:booking:results`
  - `agentic-dev:agents:sequencing:results`

And the audit should report these streams + groups as present (or created when services start consuming):
- `agentic-dev:manager:tasks` (group `manager-workers`)
- `agentic-dev:orchestrators:leads:tasks` (group `leads-workers`)
- `agentic-dev:orchestrators:outbound:tasks` (group `outbound-workers`)
- `agentic-dev:agents:rag:tasks` (group `rag-workers`)
- `agentic-dev:agents:persistence:tasks` (group `persistence_workers`)
- `agentic-dev:agents:copywriter:tasks` (group `copywriter_workers`)
- `agentic-dev:agents:booking:tasks` (group `booking-workers`)
- `agentic-dev:agents:sequencing:tasks` (group `sequencing-workers`)

**Model:** GPT-5.2 (Preview) for debugging; Codex Max for quick fixes.

## Recommended dev loop

1) Update code
2) Run `pytest tests/smoke -v`
3) Run `pytest tests/integration -v`
4) Start Docker compose and verify streams in RedisInsight

## Acceptance criteria

- RedisInsight shows streams:
  - `agentic-dev:orchestrators:outbound:tasks/results`
  - `agentic-dev:agents:booking:tasks/results`
  - `agentic-dev:agents:copywriter:tasks/results`
  - `agentic-dev:agents:sequencing:tasks/results`
- Docker starts without import errors.
- Smoke + integration tests pass.
- Manager routes outbound work to the outbound orchestrator stream.

```
