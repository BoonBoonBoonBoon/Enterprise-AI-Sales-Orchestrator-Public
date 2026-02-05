"""LangGraph workflow runner utilities.

Provides a lightweight, reusable StateGraph wrapper for Tier-2/3 agents.
This keeps Redis stream contracts unchanged while improving internal flow
control, traceability, and checkpointing.
"""

from __future__ import annotations

import inspect
import logging
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional, TypedDict

from langgraph.graph import StateGraph, END

logger = logging.getLogger(__name__)


class GraphState(TypedDict, total=False):
    execution_id: str
    task_id: str
    correlation_id: str
    input: Dict[str, Any]
    output: Dict[str, Any]
    error: str
    trace: List[Dict[str, Any]]


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _append_trace(state: GraphState, *, step: str, detail: str, **meta: Any) -> GraphState:
    trace = list(state.get("trace") or [])
    trace.append(
        {
            "step": step,
            "detail": detail,
            "timestamp": datetime.utcnow().isoformat(),
            **{k: v for k, v in meta.items() if v is not None},
        }
    )
    state["trace"] = trace
    return state


class LangGraphRunner:
    """Reusable StateGraph runner with validation, guardrails, and checkpointing."""

    def __init__(
        self,
        *,
        name: str,
        execute_fn: Callable[[GraphState], Awaitable[Dict[str, Any]] | Dict[str, Any]],
        required_input_keys: Optional[List[str]] = None,
        guardrails_fn: Optional[Callable[[GraphState], Awaitable[Dict[str, Any]] | Dict[str, Any]]] = None,
        checkpointer: Optional[Any] = None,
    ) -> None:
        self.name = name
        self.execute_fn = execute_fn
        self.required_input_keys = required_input_keys or []
        self.guardrails_fn = guardrails_fn
        self.checkpointer = checkpointer
        self._graph = None

    def _build_graph(self):
        graph = StateGraph(GraphState)

        async def validate_node(state: GraphState) -> GraphState:
            missing = []
            payload = state.get("input") or {}
            for key in self.required_input_keys:
                if payload.get(key) is None:
                    missing.append(key)
            if missing:
                state["error"] = f"missing_required_fields:{','.join(missing)}"
                return _append_trace(state, step="validate", detail="missing required fields", missing=missing)
            return _append_trace(state, step="validate", detail="ok")

        async def execute_node(state: GraphState) -> GraphState:
            if state.get("error"):
                return _append_trace(state, step="execute", detail="skipped due to error")
            try:
                result = await _maybe_await(self.execute_fn(state))
                state["output"] = result or {}
                return _append_trace(state, step="execute", detail="ok")
            except Exception as exc:  # pragma: no cover - defensive
                state["error"] = str(exc)
                return _append_trace(state, step="execute", detail="error", error=str(exc))

        async def guardrails_node(state: GraphState) -> GraphState:
            if state.get("error"):
                return _append_trace(state, step="guardrails", detail="skipped due to error")
            if not self.guardrails_fn:
                return _append_trace(state, step="guardrails", detail="no guardrails")
            try:
                result = await _maybe_await(self.guardrails_fn(state))
                if isinstance(result, dict):
                    state["output"] = result
                return _append_trace(state, step="guardrails", detail="ok")
            except Exception as exc:  # pragma: no cover
                state["error"] = str(exc)
                return _append_trace(state, step="guardrails", detail="error", error=str(exc))

        async def checkpoint_node(state: GraphState) -> GraphState:
            if not self.checkpointer:
                return state
            execution_id = state.get("execution_id") or state.get("task_id")
            if not execution_id:
                return state
            try:
                await _maybe_await(self.checkpointer.save(execution_id, dict(state)))
            except Exception as exc:  # pragma: no cover
                logger.warning("LangGraph checkpoint failed (%s): %s", self.name, exc)
            return state

        graph.add_node("validate", validate_node)
        graph.add_node("execute", execute_node)
        graph.add_node("guardrails", guardrails_node)
        graph.add_node("checkpoint", checkpoint_node)

        graph.set_entry_point("validate")
        graph.add_edge("validate", "execute")
        graph.add_edge("execute", "guardrails")
        graph.add_edge("guardrails", "checkpoint")
        graph.add_edge("checkpoint", END)

        return graph.compile()

    async def run(self, *, state_input: Dict[str, Any], execution_id: Optional[str] = None) -> Dict[str, Any]:
        if self._graph is None:
            self._graph = self._build_graph()

        state: GraphState = {
            "execution_id": execution_id or state_input.get("task_id") or state_input.get("correlation_id"),
            "task_id": state_input.get("task_id"),
            "correlation_id": state_input.get("correlation_id"),
            "input": state_input,
            "trace": [],
        }

        result_state: GraphState = await self._graph.ainvoke(state)

        if result_state.get("error"):
            return {
                "status": "error",
                "error": result_state.get("error"),
                "trace": result_state.get("trace", []),
            }

        return {
            "status": "success",
            "output": result_state.get("output", {}),
            "trace": result_state.get("trace", []),
        }
