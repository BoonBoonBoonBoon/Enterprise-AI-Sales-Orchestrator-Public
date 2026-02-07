# LLM Integration

This guide covers integrating LLMs (Large Language Models) into agents and orchestrators.

## Supported Providers

| Provider  | Status    | Models                             |
| --------- | --------- | ---------------------------------- |
| OpenAI    | ✅ Active | GPT-4o, GPT-4-turbo, GPT-3.5-turbo |
| Anthropic | ✅ Active | Claude 3.5, Claude 3 Opus/Sonnet   |

## Configuration

### Environment Variables

```bash
# OpenAI
OPENAI_API_KEY=sk-your-key-here

# Anthropic (alternative)
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Provider selection
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
LLM_TEMPERATURE=0.7
```

### Settings

```python
# config/settings.py
class Settings:
    LLM_PROVIDER: str = "openai"
    LLM_MODEL: str = "gpt-4o"
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 4096
```

## Basic Usage

### Direct LLM Call

```python
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0.7
)

response = llm.invoke([
    HumanMessage(content="Write a professional email greeting")
])

print(response.content)
```

### With Structured Output

```python
from langchain_core.pydantic_v1 import BaseModel, Field

class EmailDraft(BaseModel):
    subject: str = Field(description="Email subject line")
    body: str = Field(description="Email body")
    tone: str = Field(description="Detected tone")

llm_structured = llm.with_structured_output(EmailDraft)

result = llm_structured.invoke(
    "Draft a follow-up email to John about the demo"
)

print(f"Subject: {result.subject}")
print(f"Body: {result.body}")
```

## LangGraph Integration

### StateGraph Pattern

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
from langchain_openai import ChatOpenAI

class AgentState(TypedDict):
    messages: list
    context: dict
    output: str

def call_llm(state: AgentState) -> AgentState:
    llm = ChatOpenAI(model="gpt-4o")

    messages = state["messages"]
    response = llm.invoke(messages)

    return {
        **state,
        "output": response.content
    }

# Build graph
graph = StateGraph(AgentState)
graph.add_node("llm", call_llm)
graph.set_entry_point("llm")
graph.add_edge("llm", END)

agent = graph.compile()
```

### With Tools

```python
from langchain_core.tools import tool

@tool
def get_lead_data(lead_id: str) -> dict:
    """Retrieve lead information from database."""
    # Your implementation
    return {"name": "John", "company": "Acme"}

llm_with_tools = llm.bind_tools([get_lead_data])
```

## Agent Integration

### In Copywriter Agent

```python
class CopywriterAgent:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=os.getenv("LLM_MODEL", "gpt-4o"),
            temperature=0.7  # Higher for creative content
        )

    async def draft_reply(self, context: dict) -> dict:
        prompt = self._build_prompt(context)
        response = await self.llm.ainvoke([
            HumanMessage(content=prompt)
        ])
        return self._parse_response(response.content)

    def _build_prompt(self, context: dict) -> str:
        return f"""
        You are a professional sales representative.

        Lead: {context['name']} at {context['company']}
        Previous conversation: {context['messages']}

        Draft a personalized reply that:
        - Addresses their inquiry
        - Is professional but friendly
        - Includes a clear call to action

        Format:
        Subject: <subject line>
        Body: <email body>
        """
```

### In Manager Agent

```python
class ManagerAgent:
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.0  # Lower for classification
        )

    async def classify_intent(self, event: dict) -> str:
        prompt = f"""
        Classify this event into one of:
        inbound_inquiry, campaign_start, enrich_lead, draft_reply

        Event: {json.dumps(event)}

        Respond with just the intent name.
        """

        response = await self.llm.ainvoke([
            HumanMessage(content=prompt)
        ])

        return response.content.strip().lower()
```

## Best Practices

### Temperature Settings

| Use Case         | Temperature |
| ---------------- | ----------- |
| Classification   | 0.0         |
| Data extraction  | 0.0 - 0.2   |
| Email drafting   | 0.5 - 0.7   |
| Creative content | 0.7 - 1.0   |

### Token Management

```python
from langchain.text_splitter import TokenTextSplitter

splitter = TokenTextSplitter(
    chunk_size=3000,
    chunk_overlap=200
)

# Split long context
chunks = splitter.split_text(long_context)
```

### Error Handling

```python
from openai import RateLimitError, APIError

async def safe_llm_call(prompt: str) -> str:
    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        return response.content
    except RateLimitError:
        await asyncio.sleep(60)  # Back off
        return await safe_llm_call(prompt)  # Retry
    except APIError as e:
        logger.error(f"LLM API error: {e}")
        raise
```

### Caching

```python
from langchain.cache import SQLiteCache
from langchain.globals import set_llm_cache

# Enable caching for repeated calls
set_llm_cache(SQLiteCache(database_path=".llm_cache.db"))
```

## Testing LLM Components

### Mock LLM

```python
from unittest.mock import MagicMock

def create_mock_llm():
    mock = MagicMock()
    mock.invoke.return_value = MagicMock(
        content="Subject: Test\nBody: Hello World"
    )
    return mock
```

### Demo Script

```powershell
& ".venv/Scripts/python.exe" examples/copywriter_llm_demo.py
```

## Related

- [Copywriter Agent](../../components/tier-3/copywriter.md)
- [Manager Agent](../../components/tier-1/manager.md)
- [ADR-006: LangGraph](../../architecture/decisions/006-langgraph-deep-agents.md)
