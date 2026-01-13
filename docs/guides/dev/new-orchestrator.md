# Adding an Orchestrator

Step-by-step guide to creating a new Tier 2 orchestrator in the Agentic System.

## Overview

Tier 2 orchestrators decompose high-level goals from the Manager into sequences of Tier 3 agent tasks. They contain business logic for specific domains.

**Time:** ~45 minutes  
**Prerequisites:** Understanding of [Three-Tier Architecture](../../concepts/three-tier-architecture.md) and [Vertical Communication](../../architecture/decisions/002-vertical-only-communication.md)

## Critical Rule

!!! danger "No Horizontal Communication"
Orchestrators can **ONLY** communicate:

    - **UPWARD:** To Manager (via results)
    - **DOWNWARD:** To Tier 3 Agents (via tasks)

    Never publish to other orchestrator streams!

## Step 1: Create Folder Structure

```
tiers/tier_2/my_orchestrator/
├── __init__.py
├── orchestrator.py         # Main logic
├── consumer.py             # Entry point
├── validators.py           # Pydantic models
├── tools.py               # Agent delegation tools
└── README.md
```

```powershell
$orchPath = "tiers/tier_2/my_orchestrator"
New-Item -ItemType Directory -Force -Path $orchPath
New-Item -ItemType File -Force -Path "$orchPath/__init__.py"
New-Item -ItemType File -Force -Path "$orchPath/orchestrator.py"
New-Item -ItemType File -Force -Path "$orchPath/consumer.py"
New-Item -ItemType File -Force -Path "$orchPath/validators.py"
New-Item -ItemType File -Force -Path "$orchPath/tools.py"
New-Item -ItemType File -Force -Path "$orchPath/README.md"
```

## Step 2: Define Validators

```python
# tiers/tier_2/my_orchestrator/validators.py
from pydantic import BaseModel, Field
from typing import Optional, Literal, Any

class MyOrchestratorInput(BaseModel):
    """Input from Manager."""
    action: Literal["workflow_a", "workflow_b"]
    context: dict = Field(..., description="Workflow context")
    options: Optional[dict] = None

class MyOrchestratorOutput(BaseModel):
    """Output to Manager."""
    status: Literal["success", "error", "pending"]
    result: Optional[dict] = None
    reply_packet: Optional[dict] = None  # For chained workflows
    error_message: Optional[str] = None
```

## Step 3: Implement Delegation Tools

Create tools for calling Tier 3 agents:

```python
# tiers/tier_2/my_orchestrator/tools.py
import json
import uuid
from services.redis.client import get_redis_client

def delegate_to_agent(
    tenant_id: str,
    agent_name: str,
    action: str,
    payload: dict,
    timeout: int = 30
) -> dict:
    """
    Delegate a task to a Tier 3 agent and wait for result.

    Args:
        tenant_id: Tenant identifier
        agent_name: Name of agent (e.g., "rag", "persistence")
        action: Action for the agent to perform
        payload: Task payload
        timeout: Seconds to wait for response

    Returns:
        Agent result dictionary
    """
    redis = get_redis_client()
    task_id = str(uuid.uuid4())

    # Build task envelope
    task = {
        "task_id": task_id,
        "tenant_id": tenant_id,
        "payload": {
            "action": action,
            **payload
        },
        "metadata": {
            "source": "my_orchestrator"
        }
    }

    # Publish to agent's task stream
    task_stream = f"{tenant_id}:agents:{agent_name}:tasks"
    redis.xadd(task_stream, {"data": json.dumps(task)})

    # Wait for result on agent's result stream
    result_stream = f"{tenant_id}:agents:{agent_name}:results"

    # Poll for result (simplified - production would use consumer groups)
    import time
    start = time.time()
    while time.time() - start < timeout:
        messages = redis.xread({result_stream: "0"}, count=100, block=1000)
        for stream, msgs in messages:
            for msg_id, data in msgs:
                result = json.loads(data.get(b"data", data.get("data", "{}")))
                if result.get("task_id") == task_id:
                    return result

    raise TimeoutError(f"Agent {agent_name} did not respond within {timeout}s")


def call_rag_agent(tenant_id: str, action: str, **kwargs) -> dict:
    """Convenience wrapper for RAG agent calls."""
    return delegate_to_agent(tenant_id, "rag", action, kwargs)


def call_persistence_agent(tenant_id: str, action: str, **kwargs) -> dict:
    """Convenience wrapper for Persistence agent calls."""
    return delegate_to_agent(tenant_id, "persistence", action, kwargs)


def call_copywriter_agent(tenant_id: str, action: str, **kwargs) -> dict:
    """Convenience wrapper for Copywriter agent calls."""
    return delegate_to_agent(tenant_id, "copywriter", action, kwargs)
```

## Step 4: Implement Orchestrator Logic

```python
# tiers/tier_2/my_orchestrator/orchestrator.py
from typing import Any
from .validators import MyOrchestratorInput, MyOrchestratorOutput
from .tools import call_rag_agent, call_persistence_agent

class MyOrchestrator:
    """
    Domain-specific orchestrator for [describe domain].

    Handles:
    - workflow_a: [description]
    - workflow_b: [description]
    """

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id

    def process(self, input_data: MyOrchestratorInput) -> MyOrchestratorOutput:
        """
        Main entry point for orchestrator.
        Routes to appropriate workflow handler.
        """
        try:
            if input_data.action == "workflow_a":
                result = self._handle_workflow_a(input_data)
            elif input_data.action == "workflow_b":
                result = self._handle_workflow_b(input_data)
            else:
                return MyOrchestratorOutput(
                    status="error",
                    error_message=f"Unknown action: {input_data.action}"
                )

            return MyOrchestratorOutput(
                status="success",
                result=result,
                reply_packet=self._build_reply_packet(input_data, result)
            )

        except Exception as e:
            return MyOrchestratorOutput(
                status="error",
                error_message=str(e)
            )

    def _handle_workflow_a(self, input_data: MyOrchestratorInput) -> dict:
        """
        Workflow A: [describe the workflow]

        Steps:
        1. Get context from RAG
        2. Process data
        3. Store results
        """
        # Step 1: Get context
        rag_result = call_rag_agent(
            self.tenant_id,
            action="get_context",
            query=input_data.context.get("query", "")
        )

        # Step 2: Process (your business logic)
        processed = self._process_with_context(
            input_data.context,
            rag_result.get("result", {})
        )

        # Step 3: Store results
        persist_result = call_persistence_agent(
            self.tenant_id,
            action="write",
            table="my_table",
            data=processed
        )

        return {
            "workflow": "a",
            "processed": processed,
            "stored_id": persist_result.get("result", {}).get("id")
        }

    def _handle_workflow_b(self, input_data: MyOrchestratorInput) -> dict:
        """Workflow B implementation."""
        # Your workflow logic here
        return {"workflow": "b", "status": "completed"}

    def _process_with_context(self, context: dict, rag_context: dict) -> dict:
        """Apply business logic to combine context."""
        return {**context, "enriched_with": rag_context}

    def _build_reply_packet(self, input_data: MyOrchestratorInput, result: dict) -> dict:
        """Build reply packet for Manager to chain to other orchestrators."""
        return {
            "source_orchestrator": "my_orchestrator",
            "action_completed": input_data.action,
            "context": result
        }
```

## Step 5: Create Consumer

```python
# tiers/tier_2/my_orchestrator/consumer.py
"""
MyOrchestrator Consumer

Run with:
    python -m tiers.tier_2.my_orchestrator.consumer
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from dotenv import load_dotenv
load_dotenv()

from config.settings import settings
from services.redis.client import get_redis_client
from .orchestrator import MyOrchestrator
from .validators import MyOrchestratorInput

def main():
    tenant_id = os.getenv("TENANT_ID", settings.TENANT_ID)
    redis = get_redis_client()

    task_stream = f"{tenant_id}:orchestrators:my_orchestrator:tasks"
    result_stream = f"{tenant_id}:orchestrators:my_orchestrator:results"
    group_name = "my_orchestrator-group"
    consumer_name = f"my_orchestrator-{os.getpid()}"

    # Create consumer group if needed
    try:
        redis.xgroup_create(task_stream, group_name, mkstream=True)
    except Exception:
        pass  # Group already exists

    orchestrator = MyOrchestrator(tenant_id=tenant_id)

    print(f"MyOrchestrator listening on {task_stream}...")

    while True:
        messages = redis.xreadgroup(
            groupname=group_name,
            consumername=consumer_name,
            streams={task_stream: ">"},
            block=5000
        )

        for stream, msgs in messages:
            for msg_id, data in msgs:
                try:
                    # Parse task
                    raw = data.get(b"data", data.get("data", "{}"))
                    if isinstance(raw, bytes):
                        raw = raw.decode()
                    task = json.loads(raw)

                    print(f"Processing task: {task.get('task_id')}")

                    # Validate and process
                    input_data = MyOrchestratorInput(**task.get("payload", {}))
                    result = orchestrator.process(input_data)

                    # Publish result
                    result_envelope = {
                        "task_id": task.get("task_id"),
                        "tenant_id": tenant_id,
                        "result": result.model_dump()
                    }
                    redis.xadd(result_stream, {"data": json.dumps(result_envelope)})

                    # Acknowledge
                    redis.xack(task_stream, group_name, msg_id)

                    print(f"Completed task: {task.get('task_id')}")

                except Exception as e:
                    print(f"Error processing task: {e}")
                    # Don't ACK - will be retried

if __name__ == "__main__":
    main()
```

## Step 6: Register with Manager

Update the Manager's router to recognize your orchestrator:

```python
# In tiers/tier_1/manager/policy/router.py

ORCHESTRATOR_ROUTES = {
    "leads": "leads",
    "outreach": "outbound",  # Note: may differ from folder name
    "inbound": "inbound",
    "my_domain": "my_orchestrator",  # Add your orchestrator
}
```

## Step 7: Write Tests

```python
# tests/unit/test_my_orchestrator.py
import pytest
from tiers.tier_2.my_orchestrator.orchestrator import MyOrchestrator
from tiers.tier_2.my_orchestrator.validators import MyOrchestratorInput

class TestMyOrchestrator:
    def test_workflow_a(self, mocker):
        # Mock agent calls
        mocker.patch(
            "tiers.tier_2.my_orchestrator.tools.call_rag_agent",
            return_value={"status": "success", "result": {"context": "test"}}
        )
        mocker.patch(
            "tiers.tier_2.my_orchestrator.tools.call_persistence_agent",
            return_value={"status": "success", "result": {"id": "123"}}
        )

        orch = MyOrchestrator(tenant_id="test")
        input_data = MyOrchestratorInput(
            action="workflow_a",
            context={"query": "test query"}
        )

        result = orch.process(input_data)

        assert result.status == "success"
        assert result.result["workflow"] == "a"
```

## Stream Naming

Your orchestrator uses these streams:

| Stream | Pattern                                 | Example                                             |
| ------ | --------------------------------------- | --------------------------------------------------- |
| Input  | `{tenant}:orchestrators:{name}:tasks`   | `agentic-dev:orchestrators:my_orchestrator:tasks`   |
| Output | `{tenant}:orchestrators:{name}:results` | `agentic-dev:orchestrators:my_orchestrator:results` |

## Checklist

- [ ] Folder structure created
- [ ] Validators defined
- [ ] Delegation tools implemented
- [ ] Orchestrator logic implemented
- [ ] Consumer created
- [ ] Manager router updated
- [ ] Tests written
- [ ] README documented
- [ ] No horizontal communication (verified)

## Next Steps

- [Adding a New Agent](new-agent.md) — Create Tier 3 components
- [Communication Rules](../../architecture/decisions/002-vertical-only-communication.md) — Understand vertical communication
- [Writing Tests](testing.md) — Testing patterns
