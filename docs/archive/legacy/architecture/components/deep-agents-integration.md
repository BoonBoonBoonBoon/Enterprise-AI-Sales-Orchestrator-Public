# Deep Agents Integration - Implementation Roadmap

> **Status:** 🚧 In Progress (Phase 2, Week 3 Complete ✅)  
> **Goal:** Transform current system into multi-tier agent architecture with Manager (Tier 1) + Orchestrators (Tier 2)  
> **Timeline:** 9 weeks (3 phases)  
> **Expected Impact:** 10x faster development, 99.9% uptime, 50% fewer bugs

---

## Design Philosophy

This implementation follows **Task-Driven Architecture** principles where:

- **Agents** define WHO (roles, responsibilities, strategic decision-making)
- **Tasks** define WHAT (specific actions, sub-goals, expected outputs)
- **Tools** provide HOW (deterministic operations, data access, API calls)

**Core Design Principles:**
1. **Single Responsibility:** Each agent has clear, focused responsibilities
2. **Explicit Reasoning:** Agents explain their decision-making transparently
3. **Clear Boundaries:** Strict separation between detection (tools) and interpretation (agents)
4. **Task Independence:** Tasks can be executed and reasoned about independently
5. **Tool Reusability:** Tools remain stateless and reusable across agents

---

## Table of Contents
1. [Architecture Vision](#architecture-vision)
2. [Current State vs Target State](#current-state-vs-target-state)
3. [Implementation Phases](#implementation-phases)
4. [Step-by-Step Todo List](#step-by-step-todo-list)
5. [Key Decisions](#key-decisions)
6. [Deep Agents Integration](#deep-agents-integration)

---

## Architecture Vision

### Three-Layer Stack (Aligned with Deep Agents)

```
┌─────────────────────────────────────────────────────────────────┐
│              LAYER 1: RUNTIME (LangGraph + Deep Agents)          │
│  • Multi-step workflow orchestration                             │
│  • State persistence & checkpointing (LangGraph Store)           │
│  • Conditional routing & loops                                   │
│  • Human-in-the-loop gates (interrupt_on)                        │
│  • Planning tool (write_todos) for task decomposition            │
│  • Filesystem middleware for context management                  │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌─────────────────────────────────────────────────────────────────┐
│              LAYER 2: FRAMEWORK (LangChain + Middleware)         │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │       TIER 1: MANAGER AGENT (Strategic Deep Agent)       │  │
│  │  Built with: create_deep_agent()                         │  │
│  │  • Analyzes user goals (strategic reasoning)             │  │
│  │  • Decomposes complex tasks (TodoListMiddleware)         │  │
│  │  • Delegates to subagents (SubAgentMiddleware)           │  │
│  │  • Monitors execution & adapts plans                     │  │
│  │  • Shortcuts for simple tasks (< 50ms)                   │  │
│  │  • Context management (FilesystemMiddleware)             │  │
│  └──────────────────────┬───────────────────────────────────┘  │
│                         │                                       │
│            ┌────────────┴───────────┐                          │
│            │ (Subagent Delegation)   │                          │
│            │                        │                          │
│  ┌─────────▼─────────┐   ┌─────────▼─────────┐               │
│  │ TIER 2: CODING    │   │ TIER 2: DATA      │               │
│  │ SUBAGENT          │   │ SUBAGENT          │               │
│  │ (Specialist)      │   │ (Specialist)      │               │
│  │                   │   │                   │               │
│  │ Tools:            │   │ Tools:            │               │
│  │ • Code execution  │   │ • SQL queries     │               │
│  │ • Linting         │   │ • Pandas ops      │               │
│  │ • Testing         │   │ • Visualization   │               │
│  │ • Git operations  │   │ • ETL             │               │
│  │                   │   │                   │               │
│  │ Middleware:       │   │ Middleware:       │               │
│  │ • TodoList        │   │ • TodoList        │               │
│  │ • Filesystem      │   │ • Filesystem      │               │
│  └───────────────────┘   └───────────────────┘               │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │       TIER 2: API SUBAGENT (Integration Specialist)     │  │
│  │  Tools: HTTP requests, CRM APIs, webhooks, OAuth        │  │
│  │  Middleware: TodoList, custom API middleware            │  │
│  └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                         │
┌─────────────────────────────────────────────────────────────────┐
│        LAYER 3: INFRASTRUCTURE (Agent Harness + Deep Agents)     │
│  • Docker containerization                                       │
│  • Redis Streams task queue                                      │
│  • Observability (OpenTelemetry + LangGraph tracing)            │
│  • Error handling (retries, DLQ, circuit breakers)              │
│  • Resource management (rate limiting, quotas)                   │
│  • State checkpointing (Redis + LangGraph Store)                │
│  • Context management (Filesystem backend)                       │
└─────────────────────────────────────────────────────────────────┘
```

### Design Principles Applied

**Tool vs Agent Boundaries:**
- **Tools** (deterministic operations):
  - Execute specific operations with clear inputs/outputs
  - Encapsulate technical logic, algorithms
  - Return structured data (no decision-making)
  - Stateless and reusable across agents
  - Examples: `execute_python_code`, `query_database`, `make_http_request`

- **Agents** (strategic reasoning):
  - Make decisions about which tools to use and when
  - Interpret tool results and handle ambiguity
  - Maintain context and task state
  - Explain reasoning transparently
  - Examples: Manager Agent, Coding Subagent, Data Subagent

---

## Current State vs Target State

### Current Architecture (Manual Orchestration)

```
agent/
├── operational_agents/         # Tier 2 equivalent (manual)
│   ├── copywriter/            # Email generation
│   ├── rag_agent/             # Lead enrichment (disabled)
│   └── persistence_agent/     # Database writes
├── orchestrators/              # Single workflow_manager.py
│   └── workflow_manager.py    # Hardcoded routing
├── tools/                      # Shared utilities
└── utils/                      # Cross-cutting concerns

Characteristics:
❌ No strategic decision-making layer
❌ Hardcoded tool calls (no dynamic selection)
❌ Linear workflows (no conditionals/loops)
❌ No state persistence (fails on crash)
❌ Manual prompt engineering
```

### Target Architecture (Multi-Tier Agents)

```
agent/
├── manager/                    # ✅ NEW: Tier 1 strategic AI
│   ├── manager_agent.py       # Goal analysis & delegation
│   ├── shortcut_registry.py   # Fast paths for simple tasks
│   └── tools/                 # Delegation tools
├── orchestrators/              # ✅ ENHANCED: Tier 2 specialists
│   ├── coding_orchestrator.py # Code generation specialist
│   ├── data_orchestrator.py   # Data analysis specialist
│   ├── api_orchestrator.py    # API integration specialist
│   ├── copywriter_orchestrator.py  # Marketing specialist
│   ├── base_orchestrator.py   # LangChain agent base
│   └── workflow_manager.py    # Upgraded to LangGraph
├── runtime/                    # ✅ NEW: LangGraph workflows
│   ├── workflow_state.py      # State definitions
│   ├── workflow_graph.py      # Multi-agent workflows
│   └── checkpoints/           # State persistence
├── harness/                    # ✅ NEW: Deep Agents infra
│   ├── agent_harness.py       # Wrapper for all agents
│   ├── observability.py       # Tracing, metrics
│   └── resource_manager.py    # Quotas, rate limits
├── operational_agents/         # ✅ UPGRADED: LangChain tools
│   └── [existing agents with tool libraries]
├── tools/                      # ✅ EXPANDED: LangChain tool registry
└── utils/                      # Existing utilities

Characteristics:
✅ Manager makes strategic decisions
✅ Orchestrators use dynamic tool selection
✅ Complex workflows (loops, conditionals, human-in-the-loop)
✅ State persistence (resume on failure)
✅ Automated prompt engineering (ReAct, Chain-of-Thought)
```

---

## Implementation Phases

### Phase 1: Agent Harness (Weeks 1-2) 🏗️

**Goal:** Production-grade infrastructure for existing agents

**What Gets Built:**
- Agent wrapper with observability
- Automatic retries & DLQ routing
- State checkpointing
- Per-tenant resource quotas

**Impact:**
- 99.9% uptime (from ~95%)
- 10x faster MTTR (debugging)
- Zero-downtime deployments

---

### Phase 2: Deep Agents Framework (Weeks 3-5) 🧠

**Goal:** Deep Agent with planning, subagents, and context management

**What Gets Built:**
- Manager Agent (Tier 1) using `create_deep_agent()`
  - TodoListMiddleware for task planning
  - ShortcutRegistry for simple tasks
  - Delegation tools (current) → Subagents (future)
- Orchestrator subagents (Tier 2) with specialized tools
  - Coding Subagent with code execution tools
  - Data Subagent with query/analysis tools
  - API Subagent with integration tools
- FilesystemMiddleware for context storage
- Custom middleware for domain logic

**Impact:**
- 5x faster agent development
- Planning tool enables multi-step workflows
- Context management prevents token overflow
- 50% better email quality (adaptive copywriter)
- 30% cost reduction (fewer unnecessary API calls)

---

### Phase 3: LangGraph Runtime (Weeks 6-9) 🔄

**Goal:** Complex multi-agent workflows

**What Gets Built:**
- Workflow state machine
- Campaign workflow templates
- Human-in-the-loop approval gates
- A/B testing workflows
- Workflow visualization dashboard

**Impact:**
- 10x more complex workflows (3 steps → 30 steps)
- Resume on failure (no lost work)
- Visual workflow editor (business users)

---

## Step-by-Step Todo List

### Phase 1: Agent Harness (2 weeks)

#### Week 1: Infrastructure Setup

- [ ] **1.1 Project Setup**
  - [ ] Create `agent/harness/` folder structure
  - [ ] Install dependencies: `pip install opentelemetry-api opentelemetry-sdk`
  - [ ] Create `agent/harness/__init__.py`
  - [ ] Create `agent/harness/agent_harness.py` base class

- [ ] **1.2 Build Agent Harness Base**
  - [ ] Implement `AgentHarness` class with lifecycle management
  - [ ] Add OpenTelemetry tracing integration
  - [ ] Add Prometheus metrics (task duration, success rate)
  - [ ] Implement retry logic with exponential backoff
  - [ ] Add DLQ routing for failed tasks (after 3 retries)
  - [ ] Add graceful shutdown handler (SIGTERM)

- [ ] **1.3 State Checkpointing**
  - [ ] Create `agent/harness/checkpoints.py`
  - [ ] Implement Redis-based state persistence
  - [ ] Add checkpoint interval configuration
  - [ ] Add state restoration on startup
  - [ ] Test checkpoint → crash → resume flow

- [ ] **1.4 Resource Management**
  - [ ] Create `agent/harness/resource_manager.py`
  - [ ] Implement per-tenant CPU/memory quotas
  - [ ] Add timeout enforcement (configurable per agent)
  - [ ] Add circuit breaker for external services
  - [ ] Implement rate limiting per tenant

#### Week 2: Integration with Existing Agents

- [ ] **1.5 Wrap Copywriter Agent**
  - [ ] Update `agent/operational_agents/copywriter/worker.py`
  - [ ] Wrap in `AgentHarness` with config
  - [ ] Test tracing (view in Jaeger)
  - [ ] Test retry logic (simulate failure)
  - [ ] Test checkpointing (kill mid-task, resume)

- [ ] **1.6 Wrap Persistence Agent**
  - [ ] Update `agent/operational_agents/persistence_agent/worker.py`
  - [ ] Wrap in `AgentHarness`
  - [ ] Test DLQ routing (permanent failures)
  - [ ] Verify metrics in Grafana

- [ ] **1.7 Documentation & Testing**
  - [ ] Write `docs/AGENT_HARNESS.md` (usage guide)
  - [ ] Add unit tests (retry logic, checkpointing)
  - [ ] Add integration tests (full lifecycle)
  - [ ] Update `docs/ARCHITECTURE.md` with harness layer

---

### Phase 2: LangChain Framework (3 weeks)

#### Week 3: Manager Agent (Tier 1) ✅ COMPLETE

- [x] **2.1 Install LangChain**
  - [x] `pip install langchain>=0.1.0 langchain-openai>=0.0.5`
  - [x] Test LangChain installation
  - [x] Set up OpenAI API key in environment

- [x] **2.2 Create Manager Agent**
  - [x] Create `agent/manager/` folder
  - [x] Implement `agent/manager/manager_agent.py` (350 lines)
  - [x] Define delegation tools (coding, data, API orchestrators)
  - [x] Create Manager prompt template (goal analysis)
  - [x] Test Manager with simple goal: "What is 2 + 2?"
  - [x] Built with LangChain `create_openai_functions_agent`
  - [x] 5 delegation tools for Redis Streams enqueueing

- [x] **2.3 Shortcut Registry**
  - [x] Create `agent/manager/shortcut_registry.py` (320 lines)
  - [x] Implement shortcuts: calculations, date/time, lead lookup, health checks
  - [x] Add shortcut detection in Manager
  - [x] Test shortcut path (< 50ms latency) - Achieved <10ms
  - [x] Document shortcut patterns in `docs/MANAGER_IMPLEMENTATION.md`

- [x] **2.4 Redis Streams Integration**
  - [x] Update Manager to enqueue tasks to Redis Streams
  - [x] Define new streams: `coding:tasks`, `data:tasks`, `api:tasks`, `copywriter:tasks`
  - [x] Create DelegationTools class with multi-tenant isolation
  - [x] Test Manager → Redis → (delegation tools working)
  - [x] 18 unit tests (100% pass rate)

- [ ] **2.5 Migrate to Deep Agents** (Week 3.5 - Optional Enhancement)
  - [ ] Install deepagents: `pip install deepagents`
  - [ ] Refactor Manager to use `create_deep_agent()`
  - [ ] Add TodoListMiddleware for planning
  - [ ] Add FilesystemMiddleware for context management
  - [ ] Test planning tool: Manager breaks down complex goals
  - [ ] Document migration in `docs/DEEP_AGENTS_MIGRATION.md`

#### Week 4: Specialist Subagents (Tier 2) - Deep Agents Pattern

- [ ] **2.5 Create Base Subagent Configuration**
  - [ ] Create `agent/orchestrators/base_subagent.py`
  - [ ] Define SubAgent TypedDict schema
  - [ ] Implement subagent factory pattern
  - [ ] Add tool registry pattern
  - [ ] Add observability hooks (OpenTelemetry)
  - [ ] Document design principles (Tools vs Agents)

- [ ] **2.6 Build Coding Subagent**
  - [ ] Create `agent/orchestrators/coding_subagent.py`
  - [ ] Define tools (following Single Responsibility):
    - `execute_python_code` - Run code safely in sandbox
    - `run_linter` - Check code quality (flake8, mypy)
    - `run_tests` - Execute unit tests
    - `git_operations` - Manage version control
  - [ ] Create specialist prompt (coding expert persona)
  - [ ] Add TodoListMiddleware for multi-step tasks
  - [ ] Test with task: "Write and test Fibonacci function"
  - [ ] Verify tool calls in traces
  - [ ] Document tool boundaries (execution vs interpretation)

- [ ] **2.7 Build Data Subagent**
  - [ ] Create `agent/orchestrators/data_subagent.py`
  - [ ] Define tools (clear input/output contracts):
    - `query_database` - Execute SQL queries (structured results)
    - `analyze_dataframe` - Pandas operations (transformations)
    - `create_visualization` - Generate charts (matplotlib/plotly)
    - `etl_operations` - Extract, transform, load
  - [ ] Create specialist prompt (data analyst persona)
  - [ ] Add FilesystemMiddleware for large query results
  - [ ] Test with task: "Query leads from last month and create chart"
  - [ ] Verify SQL execution and chart generation
  - [ ] Document deterministic tool operations

- [ ] **2.8 Build API Subagent**
  - [ ] Create `agent/orchestrators/api_subagent.py`
  - [ ] Define tools (encapsulate technical logic):
    - `make_http_request` - Generic HTTP client
    - `hubspot_api` - HubSpot CRM operations
    - `salesforce_api` - Salesforce integration
    - `oauth_handler` - OAuth flow management
  - [ ] Create specialist prompt (API integration expert)
  - [ ] Add interrupt_on for sensitive operations (approval gates)
  - [ ] Test with task: "Create HubSpot contact from lead data"
  - [ ] Verify API calls and OAuth flows
  - [ ] Document stateless tool design

#### Week 5: Copywriter Subagent & Deep Agent Integration

- [ ] **2.9 Upgrade Copywriter to Deep Agent Subagent**
  - [ ] Create `agent/orchestrators/copywriter_subagent.py`
  - [ ] Define tools following Task-Driven Architecture (deterministic operations):
    - `fetch_lead_data` - Retrieve lead profile (structured query)
    - `fetch_interaction_history` - Get communication log (chronological data)
    - `check_campaign_rules` - Validate business rules (boolean checks)
    - `analyze_tone` - Sentiment analysis (classification result)
  - [ ] Add TodoListMiddleware for multi-draft workflows
  - [ ] Add FilesystemMiddleware for storing drafts and revisions
  - [ ] Create specialist prompt (copywriting expert persona)
  - [ ] Migrate existing logic with agent-centric decision making
  - [ ] Test dynamic data fetching (agent strategically selects tools)
  - [ ] Compare output quality (old vs new)
  - [ ] Document tool boundaries (data retrieval vs creative writing)

- [ ] **2.10 Manager ↔ Subagent Integration (Full Deep Agents Pattern)**
  - [ ] **Refactor Manager to use `create_deep_agent()`**:
    - Install `deepagents` package
    - Replace `create_openai_functions_agent` with `create_deep_agent()`
    - Add TodoListMiddleware for tracking delegated tasks
    - Add FilesystemMiddleware for context sharing
    - Add SubAgentMiddleware for spawning orchestrator subagents
  - [ ] **Register all subagents with Manager**:
    - Register Coding, Data, API, Copywriter subagents
    - Configure delegation tools to spawn subagents (not just queue tasks)
    - Test subagent lifecycle (spawn → execute → return results)
  - [ ] **Create orchestrator workers** (if async pattern needed):
    - Create `agent/orchestrators/orchestrator_worker.py` base
    - Implement Redis Stream listener (fallback for background tasks)
    - Add result publishing to `{orchestrator}:results` stream
    - Test Coding subagent worker
    - Test Data subagent worker
  - [ ] **End-to-End Integration Testing**:
    - Test Manager delegating to Copywriter subagent
    - Verify TodoList persistence across subagent calls
    - Verify Filesystem context sharing (Manager passes context to subagent)
    - Test planning tool usage (multi-step task breakdown)
  - [ ] Test API subagent worker

- [ ] **2.11 End-to-End Testing & Deep Agents Documentation**
  - [ ] **Integration Testing**:
    - Test Manager → Coding Subagent flow (with TodoListMiddleware)
    - Test Manager → Data Subagent flow (with FilesystemMiddleware)
    - Test Manager → API Subagent flow (with interrupt_on gates)
    - Test Manager → Copywriter Subagent flow (multi-draft workflow)
    - Verify planning tool usage across all subagents
    - Test context overflow prevention (filesystem vs memory)
  - [ ] **Performance Testing**:
    - Load test: 100 concurrent tasks across subagents
    - Measure subagent spawn latency
    - Monitor TodoList and Filesystem middleware overhead
  - [ ] **Documentation**:
    - Document in `docs/DEEP_AGENTS_INTEGRATION.md`
    - Add design principles documentation (tool vs agent boundaries)
    - Include subagent spawn patterns and best practices
    - Document middleware usage examples (TodoList, Filesystem, SubAgent)
    - Add troubleshooting guide for common integration issues

---

### Phase 3: LangGraph + Deep Agents Runtime (4 weeks)

**Integration Strategy:** Combine LangGraph's state machine capabilities with Deep Agents' planning and middleware. Use LangGraph for orchestration (routing, checkpointing, human-in-the-loop) and Deep Agents for task decomposition within nodes.

#### Week 6: LangGraph Setup & Deep Agents Integration

- [ ] **3.1 Install LangGraph & Review Architecture**
  - [ ] `pip install langgraph>=0.0.26`
  - [ ] Test LangGraph installation
  - [ ] Review LangGraph + Deep Agents integration patterns
  - [ ] Identify where LangGraph adds value vs Deep Agents planning tool

- [ ] **3.2 Define Workflow State (with Deep Agents Context)**
  - [ ] Create `agent/runtime/` folder
  - [ ] Create `agent/runtime/workflow_state.py`
  - [ ] Define `AgentWorkflowState` TypedDict
  - [ ] Add fields: 
    - goal, tenant_id, delegated_tasks, results (existing)
    - todo_list_state (for TodoListMiddleware persistence)
    - filesystem_refs (for FilesystemMiddleware context tracking)
    - subagent_spawn_history (for SubAgentMiddleware audit)
  - [ ] Document state schema with Deep Agents middleware integration

- [ ] **3.3 Build Workflow Graph (Deep Agents Nodes)**
  - [ ] Create `agent/runtime/workflow_graph.py`
  - [ ] Implement `MultiAgentWorkflow` class
  - [ ] Add nodes (each node is a Deep Agent or tool):
    - `check_shortcut` - Deterministic tool (no agent)
    - `manager_plan` - Manager Deep Agent with planning tool
    - `spawn_subagent` - SubAgentMiddleware node
    - `aggregate_results` - Deterministic tool
  - [ ] Add conditional edges (shortcut vs delegate)
  - [ ] Test workflow compilation with Deep Agents

- [ ] **3.4 State Persistence (Deep Agents Checkpointing)**
  - [ ] Configure LangGraph checkpointer (Redis backend)
  - [ ] Integrate with Deep Agents middleware state:
    - Persist TodoListMiddleware state in Redis
    - Store FilesystemMiddleware metadata (refs, not content)
    - Track SubAgentMiddleware spawn history
  - [ ] Test checkpoint → crash → resume (verify middleware state restored)
  - [ ] Add checkpoint visualization in Grafana (show middleware overhead)
  - [ ] Document checkpoint strategy with middleware considerations

#### Week 7: Campaign Workflows with Deep Agents Subagents

- [ ] **3.5 Simple Campaign Workflow (Deep Agents Pattern)**
  - [ ] Create `agent/runtime/campaigns/simple_campaign.py`
  - [ ] Build workflow with Deep Agents nodes:
    - Node 1: `fetch_leads` (Data Subagent with FilesystemMiddleware for large results)
    - Node 2: `enrich_leads` (Data Subagent with query tools)
    - Node 3: `generate_email` (Copywriter Subagent with TodoListMiddleware)
    - Node 4: `send_email` (API Subagent with interrupt_on for approval)
  - [ ] Use LangGraph for node sequencing, Deep Agents for within-node logic
  - [ ] Test with 10 test leads
  - [ ] Verify all leads processed and middleware state clean

- [ ] **3.6 Multi-Touch Campaign (with TodoListMiddleware)**
  - [ ] Create `agent/runtime/campaigns/multi_touch.py`
  - [ ] Build workflow: Email → Wait 3 days → LinkedIn → Wait 2 days → Call
  - [ ] Use TodoListMiddleware to track campaign progress per lead
  - [ ] Add wait nodes (asyncio.sleep) in LangGraph
  - [ ] Spawn Copywriter Subagent for each touch (email, LinkedIn, call script)
  - [ ] Test with accelerated timeline (seconds instead of days)
  - [ ] Verify sequence order and TodoList state persistence

- [ ] **3.7 A/B Testing Workflow (with Planning Tool)**
  - [ ] Create `agent/runtime/campaigns/ab_test.py`
  - [ ] Use Manager's planning tool to design A/B test strategy
  - [ ] Add variant assignment node (deterministic tool)
  - [ ] Add conditional routing (A vs B) in LangGraph
  - [ ] Spawn Copywriter Subagent twice (variant A and B)
  - [ ] Use FilesystemMiddleware to store variants for comparison
  - [ ] Track variant performance with deterministic analytics tool
  - [ ] Test with 20 leads (10 per variant)
  - [ ] Test with 50% split

#### Week 8: Human-in-the-Loop & Quality Control (with interrupt_on)

- [ ] **3.8 Approval Gates (LangGraph interrupt_on + Deep Agents)**
  - [ ] Create `agent/runtime/approval/human_review.py`
  - [ ] Configure LangGraph `interrupt_on` for approval nodes
  - [ ] Use Deep Agents SubAgentMiddleware to spawn reviewer subagent
  - [ ] Build approval API endpoint (`POST /approve/{task_id}`)
  - [ ] Add approval UI (simple web form)
  - [ ] Persist approval state in TodoListMiddleware
  - [ ] Test: High-value lead → Pause → Manager reviews → Approve → Continue

- [ ] **3.9 Quality Control Loop (with Planning Tool)**
  - [ ] Create `agent/runtime/quality/reviewer.py`
  - [ ] Use Manager's planning tool to define quality criteria
  - [ ] Add quality scoring node (deterministic tool, not agent)
  - [ ] Add conditional loop in LangGraph (regenerate if score < 0.8)
  - [ ] Use TodoListMiddleware to track regeneration attempts
  - [ ] Test: Generate → Score low → Regenerate → Score high → Send
  - [ ] Verify max 3 regenerations via TodoList

- [ ] **3.10 Error Recovery Workflows (Deep Agents Pattern)**
  - [ ] Add error handling nodes (deterministic retry logic)
  - [ ] Use Manager's planning tool for fallback strategy decisions
  - [ ] Implement fallback strategies:
    - Retry with backoff (deterministic tool)
    - Skip and alert (deterministic tool)
    - DLQ with context (use FilesystemMiddleware for error context)
  - [ ] Test: Task fails → Manager decides retry vs skip → Execute
  - [ ] Document error handling patterns (tool vs agent decisions)

#### Week 9: Visualization & Production Deployment

- [ ] **3.11 Workflow Visualization (with Deep Agents Middleware Tracking)**
  - [ ] Generate GraphViz diagrams from workflows
  - [ ] Add Deep Agents middleware visualization:
    - TodoListMiddleware: Show task decomposition trees
    - FilesystemMiddleware: Show context storage usage
    - SubAgentMiddleware: Show subagent spawn hierarchy
  - [ ] Create `/workflows` dashboard endpoint
  - [ ] Show active workflows with current state (include middleware overhead)
  - [ ] Add workflow execution history
  - [ ] Document in `docs/WORKFLOW_VISUALIZATION.md`

- [ ] **3.12 Docker Configuration (Deep Agents Dependencies)**
  - [ ] Create `docker-compose.agents.yml`
  - [ ] Add services: manager, coding_subagent, data_subagent, api_subagent, copywriter_subagent
  - [ ] Configure environment variables:
    - OPENAI_API_KEY
    - REDIS_URL (for checkpoints and middleware state)
    - FILESYSTEM_MIDDLEWARE_PATH (for context storage)
  - [ ] Install `deepagents` package in all containers
  - [ ] Test full stack startup
  - [ ] Verify all agents connected and middleware initialized

- [ ] **3.13 Production Deployment (with Deep Agents Monitoring)**
  - [ ] Create Kubernetes manifests
  - [ ] Configure HPA (horizontal pod autoscaler) per agent role
  - [ ] Add health check endpoints:
    - `/health` - Basic liveness
    - `/health/middleware` - Middleware state check (TodoList, Filesystem)
    - `/health/subagents` - Subagent registry status
  - [ ] Deploy to staging environment
  - [ ] Run smoke tests (include middleware overhead tests)
  - [ ] Monitor for 24 hours (track planning tool usage, context overflow prevention)

- [ ] **3.14 Documentation & Training (Deep Agents Best Practices)**
  - [ ] Write `docs/DEEP_AGENTS_COMPLETE.md` (final guide)
    - Architecture overview (Task-Driven Architecture)
    - Tool vs Agent decision framework
    - Middleware selection guide (TodoList, Filesystem, SubAgent)
    - Planning tool usage patterns
    - Common pitfalls and solutions
  - [ ] Create video walkthrough (15 min)
  - [ ] Document common troubleshooting:
    - Context overflow issues
    - Planning tool not being called
    - SubAgentMiddleware spawn failures
  - [ ] Update `docs/PROJECT_CV.md` with Deep Agents achievement
  - [ ] Team training session (hands-on with create_deep_agent())

---

## Deep Agents Integration

### Using `create_deep_agent()` for Manager Agent

The Manager Agent will be built using LangChain's `create_deep_agent()` factory, which provides:

1. **Built-in Planning** (TodoListMiddleware)
   - `write_todos` tool for task decomposition
   - Dynamic plan adaptation as new information emerges
   - Transparent reasoning about what's done and what's next

2. **Context Management** (FilesystemMiddleware)
   - `ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep` tools
   - Offload large context to memory (prevent context overflow)
   - Persistent storage for variable-length tool results

3. **Subagent Spawning** (SubAgentMiddleware)
   - Context isolation for specialist tasks
   - Keep Manager's context clean
   - Custom prompts and tools per subagent

4. **Custom Middleware** (Extensible)
   - Add domain-specific middleware
   - Custom tool descriptions
   - Additional state management

### Manager Agent Configuration

```python
from deepagents import create_deep_agent
from langchain.chat_models import init_chat_model

# Initialize model
model = init_chat_model("openai:gpt-4o", temperature=0)

# Define subagents (Tier 2 orchestrators)
coding_subagent = {
    "name": "coding-orchestrator",
    "description": "Specialist for code generation, testing, and execution",
    "prompt": """You are an expert coding assistant. Use your tools to:
    - Execute Python code safely
    - Run linters and tests
    - Manage Git operations
    - Debug and fix issues""",
    "tools": [execute_python_code, run_linter, run_tests, git_operations],
    "model": "openai:gpt-4o",
    "middleware": [TodoListMiddleware()],
}

data_subagent = {
    "name": "data-orchestrator",
    "description": "Specialist for data queries, analysis, and visualization",
    "prompt": """You are an expert data analyst. Use your tools to:
    - Query databases efficiently
    - Analyze data with pandas
    - Create visualizations
    - Handle ETL operations""",
    "tools": [query_database, analyze_dataframe, create_viz, etl_tool],
    "model": "openai:gpt-4o-mini",
    "middleware": [TodoListMiddleware()],
}

api_subagent = {
    "name": "api-orchestrator",
    "description": "Specialist for API integrations and webhooks",
    "prompt": """You are an expert API integration specialist. Use your tools to:
    - Make HTTP requests
    - Handle OAuth flows
    - Sync with CRM systems
    - Process webhooks""",
    "tools": [make_http_request, hubspot_api, salesforce_api, oauth_tool],
    "model": "openai:gpt-4o-mini",
    "middleware": [TodoListMiddleware()],
}

# Create Manager Agent (Tier 1)
manager = create_deep_agent(
    model=model,
    system_prompt="""You are a strategic AI SDR system manager. Your role:

1. Analyze user goals and break them into tasks
2. Delegate to specialist subagents:
   - coding-orchestrator: For code generation, testing, execution
   - data-orchestrator: For data queries, analysis, visualization
   - api-orchestrator: For CRM integrations, API calls
3. Use shortcuts for simple tasks (calculations, time queries)
4. Maintain context and adapt plans as work progresses
5. Explain your reasoning at each step

Always use the write_todos tool to plan complex tasks.""",
    tools=[
        # Shortcut tools (simple, fast operations)
        calculate,
        get_current_time,
        get_lead_from_cache,
        # Delegation is handled via subagents
    ],
    subagents=[coding_subagent, data_subagent, api_subagent],
    interrupt_on={
        # Require approval for sensitive operations
        "hubspot_api": {"allowed_decisions": ["approve", "edit", "reject"]},
        "salesforce_api": {"allowed_decisions": ["approve", "edit", "reject"]},
    },
)

# Invoke manager
result = manager.invoke({
    "messages": [{"role": "user", "content": "Generate outreach emails for tech leads"}]
})
```

### Subagent vs Tool: Decision Framework

**Use a Subagent when:**
- Task requires multiple steps or complex reasoning
- Need context isolation (keep Manager context clean)
- Task benefits from specialized prompts/instructions
- Multiple related tools should be used together
- Examples: Code generation workflow, Data analysis pipeline, API integration sequence

**Use a Tool when:**
- Single, deterministic operation
- No reasoning required (just execution)
- Fast operation (< 1 second)
- Should be reusable across multiple agents
- Examples: Execute Python code, Query database, Make HTTP request

**Current Implementation (Manager Agent - Complete ✅):**
- Manager uses **delegation tools** (not subagents yet)
- Tools enqueue tasks to Redis Streams
- Orchestrators consume tasks asynchronously
- **Next step:** Migrate to `create_deep_agent()` with subagents

---

## Key Decisions

### Decision 1: Deep Agents vs Manual Agent Creation

**Options:**
1. **Use `create_deep_agent()` from Deep Agents Package** (Recommended)
   - Pros: 
     - Built-in TodoListMiddleware for task decomposition
     - Built-in FilesystemMiddleware for context overflow prevention
     - Built-in SubAgentMiddleware for spawning specialist subagents
     - Planning tool for multi-step reasoning
     - Production-tested patterns from Deep Agents architecture
   - Cons: External dependency (but well-maintained)
   - Recommendation: ✅ Migrate Manager and all subagents to Deep Agents

2. **Manual `create_openai_functions_agent()` with Custom Tools**
   - Pros: Full control, no dependencies
   - Cons: Reinventing middleware patterns, no planning tool
   - Recommendation: ❌ Only for simple, single-purpose agents

**Decision:** Use Deep Agents framework for all strategic agents (Manager and orchestrator subagents). Keep simple agents (e.g., error recovery) as manual LangChain agents.

**Migration Path:**
- Week 3 (Complete): Built Manager with manual LangChain agent
- Week 3.5 (Optional): Migrate Manager to `create_deep_agent()`
- Week 5: Build all new subagents with `create_deep_agent()` from the start

---

### Decision 2: Agent Harness - Build vs Buy

**Options:**
1. **Build Custom Harness** (Recommended)
   - Pros: Full control, no external dependencies
   - Cons: 2 weeks upfront investment
   - Recommendation: ✅ Build it (you already have 80% in BaseWorker)

2. **Use External Framework** (e.g., CrewAI, AutoGen)
   - Pros: Faster initial setup
   - Cons: Less flexibility, lock-in
   - Recommendation: ❌ Not recommended

**Decision:** Build custom harness based on existing `BaseWorker` pattern.

---

### Decision 3: Tool vs Agent Boundaries (Task-Driven Architecture)

**Framework:**
- **Tools (HOW):** Deterministic operations that execute, detect, or return structured data
  - Examples: `query_database`, `execute_python_code`, `make_http_request`
  - Characteristics: Clear input/output, no ambiguity, single responsibility
  - Decision logic: NO strategic decisions, only technical execution

- **Agents (WHO):** Strategic coordinators that interpret, plan, and handle ambiguity
  - Examples: Manager, Coding Subagent, Data Subagent
  - Characteristics: Planning tool usage, context management, delegation
  - Decision logic: YES strategic decisions, task decomposition, error recovery

**Decision Rules:**
1. **If logic is deterministic** → Build as Tool
   - Example: "Run SQL query and return results" → `query_database` tool
   
2. **If logic requires interpretation** → Build as Agent
   - Example: "Analyze sales data and create insights" → Data Subagent (uses query tool)

3. **If logic is multi-step with dependencies** → Build as Agent with TodoListMiddleware
   - Example: "Write, test, and deploy code" → Coding Subagent (uses multiple tools)

**Decision:** Follow Task-Driven Architecture strictly. All new tools must be deterministic. All new subagents must use `create_deep_agent()` with planning tool.

---

### Decision 4: Manager Agent - Single vs Multiple Instances

**Options:**
1. **Single Manager Instance** (Recommended)
   - Pros: Simpler coordination, no state conflicts
   - Cons: Single point of failure
   - Recommendation: ✅ Start with single, add HA later

2. **Multiple Manager Instances**
   - Pros: High availability
   - Cons: Complex coordination (distributed locks)
   - Recommendation: ❌ Wait until Phase 3

**Decision:** Single Manager instance with quick restart (< 5 seconds).

---

### Decision 5: Model Selection per Agent Role

**Options:**
1. **GPT-4o for All Agents** (Highest Quality)
   - Cost: $0.01/1K input tokens, $0.03/1K output
   - Use case: High-value strategic tasks (Manager, Copywriter)

2. **GPT-4o-mini for Routine Subagents** (Balanced)
   - Cost: $0.002/1K input tokens, $0.006/1K output
   - Use case: Routine orchestrator tasks (Data queries, API calls)

3. **GPT-3.5-turbo for Simple Operations** (Cheapest)
   - Cost: $0.001/1K input tokens, $0.002/1K output
   - Use case: Shortcuts, low-complexity routing

**Decision (Aligned with Task-Driven Architecture):**
- **Manager Agent:** GPT-4o (strategic decisions, planning tool usage)
- **Coding Subagent:** GPT-4o (code quality critical, multi-step workflows)
- **Data Subagent:** GPT-4o-mini (routine queries, deterministic tools)
- **API Subagent:** GPT-4o-mini (simple API calls, OAuth flows)
- **Copywriter Subagent:** GPT-4o (email quality critical, creative reasoning)
- **Shortcuts (Manager):** No LLM call (deterministic pattern matching)

**Deep Agents Considerations:**
- Planning tool usage requires capable model (GPT-4o recommended)
- TodoListMiddleware overhead minimal with GPT-4o-mini
- FilesystemMiddleware reduces context size → cheaper with GPT-4o-mini

---

### Decision 6: Middleware Selection (Deep Agents Pattern)

**Available Middleware:**
1. **TodoListMiddleware**
   - Use case: Multi-step tasks requiring decomposition
   - Agents: Manager (tracking delegations), Coding Subagent (write → test → deploy)
   - Benefit: Explicit task state, resume capability

2. **FilesystemMiddleware**
   - Use case: Large context (query results, code files, drafts)
   - Agents: Data Subagent (large query results), Copywriter Subagent (drafts)
   - Benefit: Prevents context overflow, cheaper than in-memory context

3. **SubAgentMiddleware**
   - Use case: Spawning specialist subagents dynamically
   - Agents: Manager (spawning orchestrators), Coding Subagent (spawning test runners)
   - Benefit: Isolation, parallel execution

**Decision:**
- **Manager:** TodoList + Filesystem + SubAgent (all three for full capability)
- **Coding Subagent:** TodoList + Filesystem (multi-step workflows, file context)
- **Data Subagent:** Filesystem only (large query results)
- **API Subagent:** None (stateless API calls, no context overflow)
- **Copywriter Subagent:** TodoList + Filesystem (multi-draft workflow, revision history)

---

### Decision 7: State Persistence - Redis vs PostgreSQL

**Options:**
1. **Redis for Checkpoints & Middleware State** (Recommended)
   - Pros: Fast, built-in TTL, already using Redis
   - Cons: In-memory (need persistence enabled)
   - Recommendation: ✅ Use Redis with RDB snapshots for checkpoints and TodoList state

2. **PostgreSQL for Checkpoints**
   - Pros: Durable, queryable
   - Cons: Slower, overkill for checkpoints
   - Recommendation: ❌ Use for audit logs only

**Decision:** 
- Redis for checkpoints and Deep Agents middleware state (TodoList, Filesystem metadata)
- PostgreSQL for audit trail and long-term analytics
- Filesystem (local or S3) for FilesystemMiddleware content storage

---

### Decision 8: Workflow Complexity - Start Simple with Deep Agents Planning

**Phased Approach:**
1. **Phase 2 (Week 3-5):** Linear delegation with Planning Tool
   - Manager uses planning tool to decompose task
   - Manager → Single Subagent → Result
   - Subagent uses TodoListMiddleware for internal steps

2. **Phase 3 (Week 6-7):** Add conditionals with LangGraph
   - Manager → (Subagent A OR Subagent B) → Result
   - LangGraph handles routing logic based on agent output

3. **Phase 3 (Week 8):** Add loops & approvals with interrupt_on
   - Manager → Subagent → Quality Check → (Loop OR Approve) → Result
   - interrupt_on for human approval gates

4. **Phase 3 (Week 9):** Multi-step sequences with checkpointing
   - Manager → SubAgent A → SubAgent B → SubAgent C → Approve → Result
   - LangGraph checkpointing for resume capability

**Decision:** Leverage Deep Agents planning tool for task decomposition (Phase 2), then add LangGraph for complex routing/approvals (Phase 3). Don't build complex workflows upfront—evolve based on real use cases.

**Key Insight:** Deep Agents planning tool handles many "complex workflow" needs without LangGraph. Reserve LangGraph for scenarios requiring explicit state machines, human-in-the-loop, or parallelization.

---

## Success Metrics

### Phase 1 (Harness) Success Criteria

- [ ] All agents wrapped in harness
- [ ] Uptime > 99.5% (from 95%)
- [ ] MTTR < 5 minutes (from 50 minutes)
- [ ] Traces visible in Jaeger for all tasks
- [ ] Checkpoints tested (kill → resume)

### Phase 2 (Deep Agents Framework) Success Criteria

- [x] Manager successfully routes 95%+ of goals (✅ Shortcuts: 100% accuracy, <10ms latency)
- [x] Manager agent implemented with LangChain (✅ 350 lines, 18 tests passing)
- [ ] Manager migrated to `create_deep_agent()` with TodoList/Filesystem middleware
- [ ] All subagents use tools dynamically (no hardcoded calls)
- [ ] Planning tool usage rate > 80% for multi-step tasks
- [ ] Context overflow prevented (FilesystemMiddleware usage > 0% for large tasks)
- [ ] Copywriter quality improves (A/B test with TodoListMiddleware tracking)
- [ ] Cost reduced by 20%+ (fewer unnecessary API calls, better context management)
- [ ] Agent development time < 1 day (down from 1 week)
- [ ] Tool vs Agent boundaries documented (100% of tools are deterministic)

**Deep Agents-Specific Metrics:**
- [ ] TodoListMiddleware usage: > 50% of multi-step tasks use todo lists
- [ ] FilesystemMiddleware effectiveness: Context size reduced by > 30% for large tasks
- [ ] SubAgentMiddleware spawn rate: > 10 subagent spawns per hour during peak
- [ ] Planning tool effectiveness: > 90% of plans successfully executed

### Phase 3 (LangGraph + Deep Agents) Success Criteria

- [ ] 5+ complex workflows deployed (using LangGraph + Deep Agents patterns)
- [ ] Human-in-the-loop approval working (interrupt_on with Deep Agents)
- [ ] A/B testing automated (planning tool generates test strategies)
- [ ] Workflow visualization dashboard live (includes middleware tracking)
- [ ] State persistence tested (24-hour campaign survives restart with middleware state)
- [ ] LangGraph checkpointing integrated with Deep Agents middleware state
- [ ] Error recovery tested (Manager uses planning tool for fallback strategies)
- [ ] Quality control loops tested (deterministic scoring + agent-based regeneration)

**Deep Agents + LangGraph Integration Metrics:**
- [ ] Middleware overhead < 50ms per checkpoint
- [ ] Planning tool used in > 70% of LangGraph decision nodes
- [ ] Subagent spawn success rate > 95%
- [ ] Context sharing between nodes via FilesystemMiddleware working (100% success rate)

---

## Next Steps

1. **Review this roadmap** with team (30 min meeting)
2. **Assign owners** for each phase
3. **Set up development environment** (Phase 1, Week 1)
4. **Start Phase 1, Task 1.1** (Project Setup)

**Estimated Start Date:** Week of November 4, 2025  
**Estimated Completion:** Week of January 27, 2026  
**Total Duration:** 9 weeks

---

## Resources

### Documentation
- LangChain Docs: https://python.langchain.com/docs/
- LangGraph Docs: https://langchain-ai.github.io/langgraph/
- OpenTelemetry: https://opentelemetry.io/docs/instrumentation/python/

### Internal Docs
- `docs/ARCHITECTURE.md` - Current system architecture
- `docs/PROJECT_CV.md` - Project overview
- `docs/REFACTOR_ORCHESTRATORS.md` - Recent refactoring
- `DEEPAGENTS.md` - Deep Agents concept overview

### Related Files
- `agent/orchestrators/workflow_manager.py` - Current orchestrator (to be upgraded)
- `agent/operational_agents/copywriter/worker.py` - Current copywriter (to be wrapped)
- `agent/utils/typed_envelope.py` - Existing envelope pattern (compatible)

---

**Status:** Ready to begin Phase 1 ✅
