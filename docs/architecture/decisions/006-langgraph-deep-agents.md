# ADR-006: LangGraph for Deep Agents

**Status:** ✅ Accepted  
**Date:** December 2025

## Context

Some workflows require stateful, multi-step execution:

1. **RAG workflows** — Query → Retrieve → Rank → Synthesize
2. **Complex orchestration** — Multiple agent calls with branching logic
3. **Human-in-the-loop** — Pause, get approval, resume
4. **Error recovery** — Checkpoint and resume from failure

Simple function calls don't handle state persistence, branching, or interruption well.

## Decision

We use **LangGraph** for stateful, multi-step agent workflows:

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict

class RAGState(TypedDict):
    query: str
    documents: list
    answer: str

def retrieve(state: RAGState) -> RAGState:
    docs = vector_search(state["query"])
    return {"documents": docs}

def synthesize(state: RAGState) -> RAGState:
    answer = llm_synthesize(state["query"], state["documents"])
    return {"answer": answer}

# Build graph
graph = StateGraph(RAGState)
graph.add_node("retrieve", retrieve)
graph.add_node("synthesize", synthesize)
graph.add_edge("retrieve", "synthesize")
graph.add_edge("synthesize", END)
graph.set_entry_point("retrieve")

app = graph.compile()
```

### Integration with Harness

```python
from core.harness.deep_agent_harness import DeepAgentHarness

class RAGAgentHarness(DeepAgentHarness):
    def __init__(self, tenant_id: str):
        super().__init__(
            tenant_id=tenant_id,
            agent_name="rag",
            graph=rag_graph,  # LangGraph compiled app
        )
```

### When to Use LangGraph

| Use Case               | LangGraph? | Reason                             |
| ---------------------- | ---------- | ---------------------------------- |
| Simple CRUD            | ❌         | Direct function call is simpler    |
| Multi-step RAG         | ✅         | State between steps, checkpointing |
| Branching logic        | ✅         | Conditional edges                  |
| Human-in-the-loop      | ✅         | Interrupt and resume               |
| Long-running workflows | ✅         | Checkpoint on failure              |

## Consequences

### Positive

- **State management** — Built-in state passing between nodes
- **Checkpointing** — Persist state, resume on failure
- **Visualization** — Graph can be visualized for debugging
- **Branching** — Conditional edges for complex logic
- **Streaming** — Token-level streaming from LLM nodes
- **Debugging** — Clear execution trace

### Negative

- **Learning curve** — New abstraction to learn
- **Overhead** — More complex than simple functions
- **Dependency** — Tied to LangGraph library
- **Versioning** — Graph schema changes need migration

### Neutral

- **LangChain ecosystem** — Part of LangChain, shares patterns
- **Python-only** — No TypeScript/other language support

## Alternatives Considered

### Option A: Plain Python Functions

Sequential function calls with manual state passing.

- **Pros:** No new dependencies, simple
- **Cons:** No checkpointing, manual state management, no visualization
- **Why rejected:** Doesn't handle complex workflows well

### Option B: Prefect/Airflow

Full workflow orchestration platforms.

- **Pros:** Mature, rich UI, scheduling
- **Cons:** Heavy, designed for batch jobs, not real-time agents
- **Why rejected:** Overkill, latency not suitable for agents

### Option C: Custom State Machine

Build our own state machine library.

- **Pros:** Full control, no dependencies
- **Cons:** Significant engineering effort, reinventing wheel
- **Why rejected:** LangGraph already solves this well

### Option D: Temporal.io

Durable execution platform.

- **Pros:** Very robust, production-proven
- **Cons:** Separate infrastructure, complex setup
- **Why rejected:** Too heavy for current scale

## Implementation Patterns

### Conditional Edges

```python
def should_retrieve_more(state: RAGState) -> str:
    if len(state["documents"]) < 3:
        return "retrieve"  # Loop back
    return "synthesize"  # Move forward

graph.add_conditional_edges(
    "retrieve",
    should_retrieve_more,
    {"retrieve": "retrieve", "synthesize": "synthesize"}
)
```

### Checkpointing

```python
from langgraph.checkpoint import MemorySaver

checkpointer = MemorySaver()
app = graph.compile(checkpointer=checkpointer)

# Run with thread_id for checkpointing
config = {"configurable": {"thread_id": task_id}}
result = app.invoke(initial_state, config)
```

### Human-in-the-Loop

```python
graph.add_node("human_review", human_review_node)
graph.add_edge("draft", "human_review")
# Execution pauses at human_review until approved
```

## References

- [LangGraph Documentation](https://python.langchain.com/docs/langgraph)
- [LangGraph GitHub](https://github.com/langchain-ai/langgraph)
- [ADR-005: Agent Harness Pattern](005-agent-harness-pattern.md)
