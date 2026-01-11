from typing import Any, Dict
from .base_orchestrator import BaseOrchestrator


class ReplyOrchestrator(BaseOrchestrator):
    """Orchestrator that generates replies (email/text) using a copywriter agent.
    Access to - RAG, Copy, Delivery, Ingest, Monitoring, Analytics, Personality
    
    Expected input payload:
      {
        "channel": "email" | "text",
        "context": { ... }  # passed to copywriter
      }

    Returns canonical envelope: {"metadata": {...}, "records": [ {"channel":..., "content":..., "provenance": {...}} ]}
    """

    def run(self, request: Any) -> Dict[str, Any]:
        payload = request if isinstance(request, dict) else {"context": {"text": str(request)}}
        channel = payload.get("channel", "email")
        context = payload.get("context", {})

        # fetch copywriter from registry
        copywriter = self.get_agent("copywriter")
        if copywriter is None:
            raise RuntimeError("copywriter agent not available in registry")
        if channel == "email":
            msg = copywriter.write_email(context)
            record = {"channel": "email", "content": msg, "provenance": {"agent": "copywriter"}}
        else:
            txt = copywriter.write_text(context)
            record = {"channel": "text", "content": txt, "provenance": {"agent": "copywriter"}}

        env = {"metadata": {"source": "reply_orchestrator"}, "records": [record]}

        # optionally deliver using a delivery adapter from the registry
        deliver = payload.get("deliver", False)
        if deliver:
            delivery_adapter = self.get_agent("delivery")
            if delivery_adapter is None:
                env["metadata"]["delivery"] = {"status": "NO_ADAPTER"}
            else:
                # call adapter; adapters expected to return a dict result
                try:
                    res = delivery_adapter.send(channel, record["content"], {"run_source": "reply_orchestrator"})
                    env["metadata"]["delivery"] = res
                except Exception as exc:
                    env["metadata"]["delivery"] = {"status": "ERROR", "error": str(exc)}

        return env


ORCHESTRATOR_CLASS = ReplyOrchestrator
