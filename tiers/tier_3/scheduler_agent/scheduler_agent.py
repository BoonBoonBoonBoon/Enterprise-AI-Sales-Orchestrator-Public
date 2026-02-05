"""Core SchedulerAgent logic placeholder.

Responsible for booking events with external calendar providers.
"""
from __future__ import annotations

from typing import Dict, Any
import os
import asyncio
import uuid
from datetime import datetime, timezone

from tiers.tier_3.scheduler_agent.validators import ScheduleRequest, ScheduleResult


class SchedulerAgent:
    """Schedules meetings on behalf of orchestrators."""

    def __init__(self) -> None:
        self.use_langgraph = os.getenv("LANGGRAPH_WORKFLOWS_ENABLED", "1").lower() in ("1", "true", "yes")
        self._graph_runner = None

    def _get_graph_runner(self):
        if self._graph_runner is not None:
            return self._graph_runner
        from core.langgraph import LangGraphRunner

        async def _execute_graph(state):
            payload = state.get("payload") or {}
            return self.schedule(payload)

        async def _guardrails(state):
            output = state.get("output") or {}
            if not output:
                return {"status": "error", "error": "empty_schedule_result"}
            return output

        self._graph_runner = LangGraphRunner(
            name="scheduler",
            execute_fn=_execute_graph,
            required_input_keys=["payload"],
            guardrails_fn=_guardrails,
        )
        return self._graph_runner

    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.use_langgraph:
            runner = self._get_graph_runner()
            try:
                asyncio.get_running_loop()
                return self.schedule(payload)
            except RuntimeError:
                graph_result = asyncio.run(
                    runner.run(
                        state_input={
                            "payload": payload,
                            "task_id": payload.get("task_id"),
                            "correlation_id": payload.get("correlation_id"),
                        },
                        execution_id=str(payload.get("task_id") or payload.get("correlation_id") or ""),
                    )
                )
            if graph_result.get("status") == "success":
                return graph_result.get("output", {})
            return {
                "status": "error",
                "error": graph_result.get("error", "langgraph_failed"),
                "trace": graph_result.get("trace", []),
            }
        return self.schedule(payload)

    def schedule(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        request = ScheduleRequest(**payload)
        provider = (request.provider or "").lower()

        if provider in ("ical", "ics"):
            event_id = uuid.uuid4().hex
            ics = self._build_ical(request, event_id)
            result = ScheduleResult(status="success", provider=provider, event_id=event_id)
            return {**result.model_dump(), "ical": ics}

        webhook = self._provider_webhook(provider)
        if not webhook:
            result = ScheduleResult(
                status="error",
                provider=provider,
                error=f"scheduler_webhook_missing:{provider}",
            )
            return result.model_dump()

        try:
            response = self._post_webhook(webhook, request.model_dump())
            if response.get("status") in ("success", "ok"):
                result = ScheduleResult(
                    status="success",
                    provider=provider,
                    event_id=response.get("event_id"),
                )
                return {**result.model_dump(), "provider_response": response}
            result = ScheduleResult(
                status="error",
                provider=provider,
                error=response.get("error") or "scheduler_webhook_failed",
            )
            return {**result.model_dump(), "provider_response": response}
        except Exception as exc:
            result = ScheduleResult(status="error", provider=provider, error=str(exc))
            return result.model_dump()

    def _provider_webhook(self, provider: str) -> str:
        provider = provider.lower()
        env_key = f"SCHEDULER_{provider.upper()}_WEBHOOK_URL"
        return os.getenv(env_key) or os.getenv("SCHEDULER_WEBHOOK_URL", "")

    def _post_webhook(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        import requests  # type: ignore

        timeout = float(os.getenv("SCHEDULER_WEBHOOK_TIMEOUT_S", "15"))
        response = requests.post(url, json=payload, timeout=timeout)
        if response.status_code >= 200 and response.status_code < 300:
            try:
                return response.json() if response.content else {"status": "success"}
            except Exception:
                return {"status": "success"}
        return {
            "status": "error",
            "error": f"webhook_http_{response.status_code}",
            "body": response.text[:500],
        }

    def _build_ical(self, request: ScheduleRequest, event_id: str) -> str:
        def _fmt(dt: datetime) -> str:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

        uid = event_id
        return "\n".join(
            [
                "BEGIN:VCALENDAR",
                "VERSION:2.0",
                "PRODID:-//Agentic System//Scheduler//EN",
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{_fmt(datetime.utcnow().replace(tzinfo=timezone.utc))}",
                f"DTSTART:{_fmt(request.start_time)}",
                f"DTEND:{_fmt(request.end_time)}",
                f"SUMMARY:{request.event_title}",
                f"DESCRIPTION:{request.description or ''}",
                f"LOCATION:{request.location or ''}",
                "END:VEVENT",
                "END:VCALENDAR",
            ]
        )
