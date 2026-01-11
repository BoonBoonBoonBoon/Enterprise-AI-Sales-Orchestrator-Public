# Developer README

This document serves as a TODO list, a guide to the system's architecture, and a learning resource for developers working on the Agentic System. It explains the purpose of implemented features, ongoing tasks, and theories behind the design.

---

## TODO List

### High Priority
1. **Define JSON Envelope Standard**
   - **Purpose**: Standardize data exchange between agents.
   - **Details**: Create a shared `envelope.py` utility module to define the envelope structure and validation logic.
   - **Status**: Not started.
   - **Where it belongs**: `agent/utils/envelope.py`.

2. **Build Copywriter Agent**
   - **Purpose**: Generate functional email messages for leads.
   - **Details**: Use `SupabaseClient` to fetch lead data and OpenAI/LLM to generate email copy. Return results in a JSON envelope.
   - **Status**: Not started.
   - **Where it belongs**: `agent/operational_agents/copywriter_agent/`.

3. **Implement Middle-Level Orchestrator**
   - **Purpose**: Manage workflows and route tasks to operational agents.
   - **Details**: Create a `WorkflowManager` class that uses the tools/operational_agents registries to dynamically discover and invoke agents.
   - **Status**: Not started.
   - **Where it belongs**: `agent/orchestrators/`.

4. **Add Communication Layer**
   - **Purpose**: Enable agents to communicate efficiently.
   - **Details**: Start with direct function calls for simplicity. Add a message queue (e.g., RabbitMQ, Kafka) later for scalability.
   - **Status**: Not started.
   - **Where it belongs**: TBD (depends on the communication framework).

### Medium Priority
1. **Add Unit Tests for Copywriter Agent**
   - **Purpose**: Ensure the agent behaves as expected.
   - **Details**: Mock `SupabaseClient.query_table()` to test edge cases (0/1/multiple rows).
   - **Status**: Not started.
   - **Where it belongs**: `tests/test_copywriter_agent.py`.

2. **Expand Registry Tests**
   - **Purpose**: Validate discovery of all agents and tools.
   - **Details**: Add tests for edge cases (e.g., missing AGENT_CLASS, invalid exports).
   - **Status**: In progress.
   - **Where it belongs**: `tests/test_registry.py`.

3. **Add GitHub Actions Workflows**
   - **Purpose**: Automate testing for `develop/safe` and `develop/hazard` branches.
   - **Details**: Create `ci-safe.yml` for unit tests and `ci-hazard.yml` for integration tests.
   - **Status**: Not started.
   - **Where it belongs**: `.github/workflows/`.

---

## Theories and Design Decisions

### JSON Envelope Standard
- **Why**: Ensures consistent, predictable data exchange between agents.
- **Structure**:
  - `metadata`: Source, timestamp, task ID, filters.
  - `payload`: Actual data (e.g., lead info, generated copy).
  - `provenance`: Tracks data origin and integrity.
  - `status`: SUCCESS, ERROR, etc.
- **Example**:
```json
{
  "metadata": {
    "source": "supabase.leads",
    "task_id": "12345",
    "retrieved_at": "2025-09-07T12:23:59Z",
    "filters": { "id": "fd6bc6b5-e2e8-449d-93f9-2d1b6c9ac8a1" }
  },
  "payload": {
    "records": [
      {
        "id": "fd6bc6b5-e2e8-449d-93f9-2d1b6c9ac8a1",
        "email": "wez.mock@example-test.com",
        "company": "WM company",
        "first_name": "wez",
        "last_name": "mud",
        "job_title": "CEO"
      }
    ]
  },
  "provenance": {
    "source": "supabase.leads",
    "row_id": "fd6bc6b5-e2e8-449d-93f9-2d1b6c9ac8a1",
    "row_hash": "e4e13ab2b7bcd4b9f721b94f7890a8edc6ee6a9a3b5bec62d0b502b2c3289433"
  },
  "status": "SUCCESS",
  "error": null
}
```

### Agent Hierarchy
- **Management Agent**: High-level orchestrator that breaks down tasks into subtasks.
- **Middle-Level Orchestrator**: Routes tasks to the best operational agents.
- **Operational Agents**: Perform specific tasks (e.g., querying leads, generating copy).

### Communication Between Agents
- **Direct Function Calls**: Simple and fast for single-machine setups.
- **Message Queue**: Scalable and fault-tolerant for distributed systems.

---

## Learning Resources

### Existing Features
1. **Registry System**:
   - **Purpose**: Dynamically discover agents and tools.
   - **Files**:
     - `agent/operational_agents/registry.py`
     - `agent/tools/registry.py`
   - **Tests**:
     - `tests/test_registry.py`

2. **SupabaseClient**:
   - **Purpose**: Query the Supabase database.
   - **File**: `agent/tools/supabase_tools.py`

### Planned Features
1. **Copywriter Agent**:
   - **Purpose**: Generate email copy for leads.
   - **Planned Location**: `agent/operational_agents/copywriter_agent/`

2. **Middle-Level Orchestrator**:
   - **Purpose**: Manage workflows and route tasks.
   - **Planned Location**: `agent/orchestrators/`

---

## Notes for Developers
- Follow the JSON envelope standard for all data exchange.
- Write unit tests for all new features.
- Use the registries to dynamically discover agents and tools.
- Keep the system modular and scalable.


## Agent Responsibilities
Each agent should have a clear contract for inputs and outputs. This ensures that:

Agents are modular and reusable.
Orchestrators can easily compose workflows using different agents.
Management Agent
Role: High-level decision-maker. Breaks down large tasks into subtasks and assigns them to middle-level orchestrators.
Input: High-level task description (e.g., "Generate a follow-up email for all leads in the 'Acme' campaign").
Output: Subtasks for middle-level orchestrators.
Middle-Level Orchestrator
Role: Workflow manager. Decides which operational agents to use and coordinates their execution.
Input: Subtasks from the management agent.
Output: Results from operational agents, aggregated and sent back to the management agent.
Operational Agents
Role: Perform specific tasks (e.g., querying leads, generating copy).
Input: JSON envelope with task details.
Output: JSON envelope with results.