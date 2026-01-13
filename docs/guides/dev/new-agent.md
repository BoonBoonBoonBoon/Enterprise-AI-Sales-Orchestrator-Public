# Adding a New Agent

Step-by-step guide to creating a new Tier 3 agent in the Agentic System.

## Overview

Tier 3 agents are atomic execution units that perform specialized tasks. This guide walks through creating a complete agent from scratch.

**Time:** ~30 minutes  
**Prerequisites:** Understanding of [Three-Tier Architecture](../../concepts/three-tier-architecture.md) and [Agent Harness](../../concepts/agent-harness.md)

## Step 1: Create Folder Structure

Create a new folder under `tiers/tier_3/`:

```
tiers/tier_3/my_agent/
├── __init__.py
├── my_agent.py           # Core logic
├── my_agent_harness.py   # Redis wrapper
├── consumer.py           # Entry point
├── validators.py         # Pydantic models
└── README.md
```

```powershell
$agentPath = "tiers/tier_3/my_agent"
New-Item -ItemType Directory -Force -Path $agentPath
New-Item -ItemType File -Force -Path "$agentPath/__init__.py"
New-Item -ItemType File -Force -Path "$agentPath/my_agent.py"
New-Item -ItemType File -Force -Path "$agentPath/my_agent_harness.py"
New-Item -ItemType File -Force -Path "$agentPath/consumer.py"
New-Item -ItemType File -Force -Path "$agentPath/validators.py"
New-Item -ItemType File -Force -Path "$agentPath/README.md"
```

## Step 2: Define Validators

Create Pydantic models for input/output validation in `validators.py`:

```python
# tiers/tier_3/my_agent/validators.py
from pydantic import BaseModel, Field
from typing import Optional, Literal

class MyAgentInput(BaseModel):
    """Input payload for MyAgent tasks."""
    action: Literal["process", "validate", "transform"]
    data: dict = Field(..., description="Data to process")
    options: Optional[dict] = Field(default=None)

class MyAgentOutput(BaseModel):
    """Output payload from MyAgent."""
    status: Literal["success", "error"]
    result: Optional[dict] = None
    error_message: Optional[str] = None
```

## Step 3: Implement Core Logic

Write the agent's business logic in `my_agent.py`:

```python
# tiers/tier_3/my_agent/my_agent.py
from typing import Any
from .validators import MyAgentInput, MyAgentOutput

def process_task(input_data: MyAgentInput) -> MyAgentOutput:
    """
    Main processing function for MyAgent.

    Args:
        input_data: Validated input payload

    Returns:
        MyAgentOutput with results or error
    """
    try:
        if input_data.action == "process":
            result = _do_processing(input_data.data)
        elif input_data.action == "validate":
            result = _do_validation(input_data.data)
        elif input_data.action == "transform":
            result = _do_transformation(input_data.data)
        else:
            return MyAgentOutput(
                status="error",
                error_message=f"Unknown action: {input_data.action}"
            )

        return MyAgentOutput(status="success", result=result)

    except Exception as e:
        return MyAgentOutput(status="error", error_message=str(e))

def _do_processing(data: dict) -> dict:
    """Process the input data."""
    # Your logic here
    return {"processed": True, "data": data}

def _do_validation(data: dict) -> dict:
    """Validate the input data."""
    return {"valid": True}

def _do_transformation(data: dict) -> dict:
    """Transform the input data."""
    return {"transformed": data}
```

## Step 4: Create the Harness

Wrap your agent in a harness for Redis communication in `my_agent_harness.py`:

```python
# tiers/tier_3/my_agent/my_agent_harness.py
from core.harness.agent_harness import AgentHarness
from .validators import MyAgentInput, MyAgentOutput
from .my_agent import process_task

class MyAgentHarness(AgentHarness):
    """Redis stream wrapper for MyAgent."""

    def __init__(self, tenant_id: str):
        super().__init__(
            tenant_id=tenant_id,
            agent_name="my_agent",  # Stream: {tenant}:agents:my_agent:tasks
        )

    def process_task(self, task: dict) -> dict:
        """
        Process a task from the Redis stream.

        Args:
            task: Raw task envelope from stream

        Returns:
            Result dictionary to publish
        """
        try:
            # Extract and validate payload
            payload = task.get("payload", {})
            input_data = MyAgentInput(**payload)

            # Process
            output = process_task(input_data)

            # Return result
            return output.model_dump()

        except Exception as e:
            return MyAgentOutput(
                status="error",
                error_message=f"Task processing failed: {e}"
            ).model_dump()
```

## Step 5: Create Consumer Entry Point

Create the consumer that runs the agent in `consumer.py`:

```python
# tiers/tier_3/my_agent/consumer.py
"""
MyAgent Consumer

Run with:
    python -m tiers.tier_3.my_agent.consumer
"""
import os
import sys

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from dotenv import load_dotenv
load_dotenv()

from config.settings import settings
from .my_agent_harness import MyAgentHarness

def main():
    tenant_id = os.getenv("TENANT_ID", settings.TENANT_ID)

    print(f"Starting MyAgent consumer for tenant: {tenant_id}")

    harness = MyAgentHarness(tenant_id=tenant_id)
    harness.run()  # Blocks, listens on stream

if __name__ == "__main__":
    main()
```

## Step 6: Add to `__init__.py`

Export your agent components:

```python
# tiers/tier_3/my_agent/__init__.py
from .my_agent import process_task
from .my_agent_harness import MyAgentHarness
from .validators import MyAgentInput, MyAgentOutput

__all__ = [
    "process_task",
    "MyAgentHarness",
    "MyAgentInput",
    "MyAgentOutput",
]
```

## Step 7: Write Tests

Create tests in `tests/unit/test_my_agent.py`:

```python
# tests/unit/test_my_agent.py
import pytest
from tiers.tier_3.my_agent.validators import MyAgentInput, MyAgentOutput
from tiers.tier_3.my_agent.my_agent import process_task

class TestMyAgent:
    def test_process_action(self):
        input_data = MyAgentInput(
            action="process",
            data={"key": "value"}
        )
        result = process_task(input_data)

        assert result.status == "success"
        assert result.result["processed"] is True

    def test_validate_action(self):
        input_data = MyAgentInput(
            action="validate",
            data={"test": 123}
        )
        result = process_task(input_data)

        assert result.status == "success"
        assert result.result["valid"] is True

    def test_invalid_action(self):
        # This should fail validation
        with pytest.raises(ValueError):
            MyAgentInput(action="invalid", data={})

    def test_harness_integration(self):
        from tiers.tier_3.my_agent.my_agent_harness import MyAgentHarness

        harness = MyAgentHarness(tenant_id="test")
        task = {
            "task_id": "test-001",
            "payload": {
                "action": "process",
                "data": {"foo": "bar"}
            }
        }

        result = harness.process_task(task)
        assert result["status"] == "success"
```

Run tests:

```powershell
& ".venv/Scripts/python.exe" -m pytest tests/unit/test_my_agent.py -v
```

## Step 8: Document Your Agent

Create `README.md` in the agent folder:

```markdown
# MyAgent

Brief description of what this agent does.

## Purpose

Explain the agent's role in the system.

## Actions

| Action      | Input          | Output                | Description              |
| ----------- | -------------- | --------------------- | ------------------------ |
| `process`   | `{data: dict}` | `{processed: bool}`   | Processes input data     |
| `validate`  | `{data: dict}` | `{valid: bool}`       | Validates data structure |
| `transform` | `{data: dict}` | `{transformed: dict}` | Transforms data format   |

## Stream Interface

- **Input:** `{tenant}:agents:my_agent:tasks`
- **Output:** `{tenant}:agents:my_agent:results`

## Example

\`\`\`python
task = {
"task_id": "example-001",
"tenant_id": "agentic-dev",
"payload": {
"action": "process",
"data": {"key": "value"}
}
}
\`\`\`

## Running

\`\`\`powershell
& ".venv/Scripts/python.exe" -m tiers.tier_3.my_agent.consumer
\`\`\`
```

## Step 9: Register and Deploy

1. **Add to consumer scripts** (if using process manager)
2. **Add to Docker Compose** (if containerized)
3. **Update documentation** in `docs/components/tier-3/`

## Checklist

- [ ] Folder structure created
- [ ] Validators defined
- [ ] Core logic implemented
- [ ] Harness wrapper created
- [ ] Consumer entry point added
- [ ] `__init__.py` exports configured
- [ ] Unit tests written and passing
- [ ] README documented
- [ ] Integration tested with live Redis

## Common Patterns

### Database Access

If your agent needs database access, use the appropriate role:

```python
from services.persistence.supabase_adapter import SupabaseAdapter

class MyAgentHarness(AgentHarness):
    def __init__(self, tenant_id: str):
        super().__init__(tenant_id=tenant_id, agent_name="my_agent")
        self.db = SupabaseAdapter(role="agent_reader")  # or "agent_writer"
```

### LLM Calls

For agents that call LLMs:

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4o", temperature=0)
response = llm.invoke([{"role": "user", "content": prompt}])
```

### External APIs

Wrap external calls with retries:

```python
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def call_external_api(url: str, data: dict) -> dict:
    response = httpx.post(url, json=data, timeout=30)
    response.raise_for_status()
    return response.json()
```

## Next Steps

- [Adding an Orchestrator](new-orchestrator.md) — Create Tier 2 components
- [Writing Tests](testing.md) — Testing patterns
- [Agent Harness](../../concepts/agent-harness.md) — Harness configuration options
