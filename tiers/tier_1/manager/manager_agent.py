"""
Manager Agent - Tier 1 Strategic Router

The Manager Agent sits at the top of the system and is responsible for:
1. Ingesting ANY input (free text, envelopes, webhook payloads)
2. Normalizing and classifying the intent deterministically
3. Delegating work to Tier-2 orchestrators via Redis Streams
4. Tracking progress and exposing health

Design notes:
- Deterministic-first: rules/registry driven; optional LLM fallback when enabled
- Harness-wrapped by core.harness.AgentHarness for retries/observability/quota
- Shortcut registry remains for ultra-fast paths (<50ms)
- Deep agent (LangChain) remains optional as a fallback mode
"""

import json
import uuid
import logging
import time
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path

import os
import redis
try:
    from langchain.tools import tool  # optional, only used when deep agent fallback is enabled
except Exception:  # pragma: no cover
    tool = None  # type: ignore

from .shortcut_registry import ShortcutRegistry
from .tools.delegation_tools import DelegationTools
# New intake/intent/policy pipeline
from core.schemas.manager import UnifiedManagerRequest, ManagerDecision
from .intake.normalizer import normalize_input
from .intent.rules import classify_by_rules
from .intent.llm_fallback import classify_with_llm
from .policy.router import build_plan
# Observability
from core.observability import ObservabilityContext, start_metrics_server
from core.envelope import task as create_task_envelope, to_redis_fields, from_redis_message

logger = logging.getLogger(__name__)


def _trace_log(actor: str, *, correlation_id: str, task_id: str, step: str, detail: str, **kwargs: Any) -> None:
    """Structured trace logging without extra infra."""
    try:
        payload = {
            "trace": True,
            "actor": actor,
            "correlation_id": correlation_id,
            "task_id": task_id,
            "step": step,
            "detail": detail,
            "timestamp": datetime.utcnow().isoformat(),
        }
        payload.update({k: v for k, v in kwargs.items() if v is not None})
        logger.info(json.dumps(payload))
    except Exception:
        pass


class ManagerAgent:
    """
    Tier 1 Strategic AI - Manager Agent
    
    Responsibilities:
    - Goal analysis and decomposition
    - Task routing and delegation
    - Result aggregation
    - Strategic decision-making
    """
    
    def __init__(
        self,
        redis_client: redis.Redis,
        tenant_id: str = "default",
        model: str = "gpt-4o",
        temperature: float = 0.0,
        enable_llm_fallback: bool = False,
        enable_deep_agent: bool = False,
    ):
        """
        Initialize Manager Agent.
        
        Args:
            redis_client: Redis client for task delegation
            tenant_id: Tenant context for multi-tenant isolation
            model: OpenAI model (default: gpt-4o for strategic reasoning)
            temperature: LLM temperature (0.0 for deterministic)
        """
        self.redis = redis_client
        self.tenant_id = tenant_id
        self.model_name = model
        self.temperature = temperature
        self.enable_llm_fallback = enable_llm_fallback
        self.enable_deep_agent = enable_deep_agent
        
        # Initialize components
        self.shortcuts = ShortcutRegistry(redis_client)
        self.delegation = DelegationTools(redis_client, tenant_id)
        
        # Start metrics server (only once per process)
        try:
            start_metrics_server()
            logger.info("Metrics server started on port 8000")
        except Exception as e:
            logger.debug(f"Metrics server already running or failed to start: {e}")
        
        # Initialize Deep Agent only if explicitly enabled and langchain available
        self.tools = []
        self.agent = None
        self.filesystem_path = Path("./agent_context") / tenant_id
        if self.enable_deep_agent and tool is not None:
            self.tools = self._build_tools()
            try:
                # Lazy import to avoid heavy deps unless enabled
                from .deep_agent_factory import create_manager_deep_agent
                self.agent = create_manager_deep_agent(
                    tools=self.tools,
                    model=model,
                    temperature=temperature,
                    tenant_id=tenant_id,
                    filesystem_path=self.filesystem_path,
                    enable_subagents=True,
                )
                logger.info(
                    f"Manager Deep Agent initialized (model={model}, tenant={tenant_id})"
                )
                logger.info("  Middleware: TodoList + Filesystem + SubAgents")
                logger.info(f"  Context storage: {self.filesystem_path}")
            except Exception as e:  # pragma: no cover
                logger.warning(f"Deep Agent initialization skipped: {e}")
    
    def _build_tools(self) -> List:
        """
        Build delegation tools for LangChain agent.
        
        Returns:
            List of LangChain tools
        """
        # Create tool instances with closures over delegation methods
        
        @tool
        def delegate_coding_task(task: str, requirements: str = "{}") -> str:
            """
            Delegate coding/automation task to Coding Orchestrator.
            
            Use for: script generation, code refactoring, automation workflows, data processing.
            
            Args:
                task: Description of coding task
                requirements: JSON string with technical requirements (language, framework, constraints)
                
            Returns:
                Task delegation confirmation with task_id
            """
            try:
                req_dict = json.loads(requirements) if requirements != "{}" else {}
            except json.JSONDecodeError:
                req_dict = {"notes": requirements}
            
            result = self.delegation.delegate_to_coding_orchestrator(
                task=task,
                requirements=req_dict
            )
            return json.dumps(result)
        
        @tool
        def delegate_data_query(query: str, dataset: str = "leads", filters: str = "{}") -> str:
            """
            Delegate data query/analysis to Data Orchestrator.
            
            Use for: lead searches, campaign analytics, report generation, data exports.
            
            Args:
                query: Natural language query or SQL-like expression
                dataset: Target dataset (leads, campaigns, interactions)
                filters: JSON string with additional filters (date ranges, status, etc.)
                
            Returns:
                Task delegation confirmation with task_id
            """
            try:
                filter_dict = json.loads(filters) if filters != "{}" else {}
            except json.JSONDecodeError:
                filter_dict = {}
            
            result = self.delegation.delegate_to_data_orchestrator(
                query=query,
                dataset=dataset,
                filters=filter_dict
            )
            return json.dumps(result)
        
        @tool
        def delegate_api_request(endpoint: str, operation: str, parameters: str = "{}") -> str:
            """
            Delegate API integration task to API Orchestrator.
            
            Use for: CRM sync (HubSpot, Salesforce), webhook processing, third-party API calls, OAuth.
            
            Args:
                endpoint: API endpoint or integration name (e.g., 'hubspot/contacts', 'salesforce/leads')
                operation: Operation type (GET, POST, PUT, DELETE, SYNC)
                parameters: JSON string with request parameters or body
                
            Returns:
                Task delegation confirmation with task_id
            """
            try:
                param_dict = json.loads(parameters) if parameters != "{}" else {}
            except json.JSONDecodeError:
                param_dict = {}
            
            result = self.delegation.delegate_to_api_orchestrator(
                endpoint=endpoint,
                operation=operation,
                parameters=param_dict
            )
            return json.dumps(result)
        
        @tool
        def delegate_email_generation(lead_id: str, campaign_id: str, context: str = "{}") -> str:
            """
            Delegate email generation via the outbound/orchestrator pathway.

            This preserves vertical-only comms (Manager → Orchestrator → Agents)
            and avoids direct calls to Tier 3 copywriter agents.
            """
            try:
                context_dict = json.loads(context) if context != "{}" else {}
            except json.JSONDecodeError:
                context_dict = {"notes": context}

            result = self.delegation.delegate_to_outreach_orchestrator(
                goal="generate_email",
                campaign_data={
                    "lead_id": lead_id,
                    "campaign_id": campaign_id,
                    **({"context": context_dict} if context_dict else {}),
                },
            )
            return json.dumps(result)
        
        @tool
        def delegate_leads_discovery(goal: str, criteria: str = "{}") -> str:
            """
            Delegate lead discovery/qualification to Leads Orchestrator.
            
            Use for: finding new leads, lead qualification scoring, lead enrichment, list building.
            
            Args:
                goal: Lead discovery goal (e.g., "Find 50 AI startups in San Francisco")
                criteria: JSON string with search criteria (industry, location, company_size, technologies, etc.)
                
            Returns:
                Task delegation confirmation with task_id
            """
            try:
                criteria_dict = json.loads(criteria) if criteria != "{}" else {}
            except json.JSONDecodeError:
                criteria_dict = {}
            
            result = self.delegation.delegate_to_leads_orchestrator(
                goal=goal,
                criteria=criteria_dict
            )
            return json.dumps(result)
        
        @tool
        def delegate_outreach_campaign(goal: str, campaign_data: str = "{}") -> str:
            """
            Delegate campaign orchestration to Outreach Orchestrator.
            
            Use for: multi-channel campaigns, email sequences, LinkedIn outreach, phone follow-ups.
            
            Args:
                goal: Campaign goal (e.g., "Launch Q4 enterprise outreach with email, LinkedIn, phone")
                campaign_data: JSON string with campaign details (leads, channels, touchpoints, timing, etc.)
                
            Returns:
                Task delegation confirmation with task_id
            """
            try:
                campaign_dict = json.loads(campaign_data) if campaign_data != "{}" else {}
            except json.JSONDecodeError:
                campaign_dict = {}
            
            result = self.delegation.delegate_to_outreach_orchestrator(
                goal=goal,
                campaign_data=campaign_dict
            )
            return json.dumps(result)
        
        @tool
        def check_task_status(task_id: str) -> str:
            """
            Check status of previously delegated task.
            
            Args:
                task_id: Task identifier from delegation result
                
            Returns:
                Task status and result (if completed)
            """
            result = self.delegation.check_task_status(task_id)
            return json.dumps(result)
        
        return [
            delegate_coding_task,
            delegate_data_query,
            delegate_api_request,
            delegate_email_generation,
            delegate_leads_discovery,
            delegate_outreach_campaign,
            check_task_status,
        ]
    

    
    def execute(self, task_data_or_goal, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute goal with Manager Agent.
        
        Workflow:
        1. Check shortcuts for fast paths (<50ms)
        2. If not shortcut, use LangChain agent to analyze and delegate
        3. Return results or task_ids for async tracking
        
        Args:
            task_data_or_goal: User's goal/request (string) or task data dict
            context: Optional context (user_id, session_id, etc.)
            
        Returns:
            Execution result with status and output
        """
        start_time = datetime.now()
        
        # Extract goal from task_data if dict passed
        if isinstance(task_data_or_goal, dict):
            goal = task_data_or_goal.get("goal", "")
            context = context or task_data_or_goal.get("data", {})
        else:
            goal = task_data_or_goal
        
        # Log execution
        execution_id = f"exec_{start_time.timestamp()}"
        logger.info(f"Manager executing goal: {goal} (id={execution_id})")
        
        # Wrap with observability context
        with ObservabilityContext(
            tier="manager",
            component="manager_agent",
            tenant_id=self.tenant_id,
            execution_id=execution_id,
            redis_client=self.redis,
        ) as obs:
            return self._execute_with_observability(obs, goal, context, task_data_or_goal, execution_id, start_time)
    
    def _execute_with_observability(
        self,
        obs: ObservabilityContext,
        goal: str,
        context: Optional[Dict[str, Any]],
        task_data_or_goal: Any,
        execution_id: str,
        start_time: datetime
    ) -> Dict[str, Any]:
        """Internal execution with observability tracking"""
    
        # Step 1: Check shortcuts
        if self.shortcuts.can_shortcut(goal):
            logger.info("Shortcut path detected")
            shortcut_result = self.shortcuts.execute_shortcut(goal)
            
            if shortcut_result["success"]:
                elapsed = (datetime.now() - start_time).total_seconds() * 1000
                logger.info(f"Shortcut succeeded in {elapsed:.2f}ms")
                
                # Log shortcut path
                obs.log_decision(
                    path="shortcut",
                    shortcut_type=shortcut_result["shortcut_type"],
                )
                obs.track_cost(0.0)  # Shortcuts are free
                
                return {
                    "success": True,
                    "execution_id": execution_id,
                    "path": "shortcut",
                    "intent": "shortcut",
                    "confidence": 1.0,
                    "orchestrators": [],
                    "reasons": [f"shortcut:{shortcut_result.get('shortcut_type', 'unknown')}"] ,
                    "used_fallback": False,
                    "enqueued": [],
                    "result": shortcut_result["result"],
                    "shortcut_type": shortcut_result["shortcut_type"],
                    "latency_ms": elapsed,
                    "timestamp": start_time.isoformat(),
                }

        # Step 2: Deterministic pipeline (normalize → classify → optional LLM fallback → plan → emit)
        try:
            # 2a. Normalize any input to a unified request
            req: UnifiedManagerRequest = normalize_input(
                {"goal": goal, "data": context or {}, "tenant_id": self.tenant_id}
                if not isinstance(task_data_or_goal, dict)
                else task_data_or_goal,
                source="manager",
                tenant_id=self.tenant_id,
            )

            corr_id = req.correlation_id or execution_id
            _trace_log("manager", correlation_id=corr_id, task_id=execution_id, step="received", detail="manager_execute")

            # 2b. Classify by rules first
            intent, confidence, reasons = classify_by_rules(req)

            # 2c. Optional LLM fallback guardrails
            #
            # Rationale:
            # - Deterministic-first is still the default.
            # - But we want strong guardrails for ambiguous/high-impact inputs (e.g., inbound emails
            #   where a reply is allowed/expected).
            # - We also want LLM fallback to trigger at a configurable threshold, not a hard-coded < 0.5.
            llm_threshold_env = os.getenv("MANAGER_LLM_FALLBACK_CONFIDENCE_THRESHOLD", "0.6")
            try:
                llm_threshold = float(llm_threshold_env)
            except Exception:
                llm_threshold = 0.6

            force_llm_for_email = os.getenv("MANAGER_FORCE_LLM_FOR_EMAIL_EVENTS", "1").lower() in (
                "1",
                "true",
                "yes",
            )
            payload_ctx = (req.payload or {}).get("context") if isinstance(req.payload, dict) else None
            has_email_event = bool(
                isinstance(payload_ctx, dict)
                and isinstance(payload_ctx.get("email_event"), dict)
                and payload_ctx.get("email_event")
            )

            actions_allowed = []
            if isinstance(payload_ctx, dict):
                aa = payload_ctx.get("actions_allowed")
                if isinstance(aa, list):
                    actions_allowed = [str(x) for x in aa]

            should_try_llm = False
            llm_debug_summary: Optional[str] = None
            if self.enable_llm_fallback:
                if confidence <= llm_threshold:
                    should_try_llm = True
                    reasons = reasons + [f"llm:trigger:confidence<={llm_threshold}"]
                elif force_llm_for_email and has_email_event and ("reply" in actions_allowed):
                    should_try_llm = True
                    reasons = reasons + ["llm:trigger:email_event_reply_allowed"]

            # Always record that LLM fallback was attempted for observability/testing,
            # even if we ultimately keep the rules-based intent.
            if should_try_llm:
                llm_intent, llm_conf, llm_reasons = classify_with_llm(req)
                if llm_reasons:
                    reasons = reasons + llm_reasons
                if llm_conf > confidence and llm_intent != "unknown":
                    intent, confidence = llm_intent, llm_conf

                # Very brief debug-only summary (no chain-of-thought)
                trigger_bits = [r for r in reasons if isinstance(r, str) and r.startswith("llm:trigger:")]
                trigger = trigger_bits[0].replace("llm:trigger:", "") if trigger_bits else "unknown"
                llm_debug_summary = (
                    f"llm_used=true trigger={trigger} llm_intent={llm_intent}({llm_conf:.2f}) "
                    f"final_intent={intent}({confidence:.2f})"
                )
                if len(llm_debug_summary) > 180:
                    llm_debug_summary = llm_debug_summary[:177] + "..."

            # 2d. Build plan (which orchestrators to call, with payloads)
            decision: ManagerDecision = build_plan(intent, confidence, reasons, req)

            # 2e. Emit tasks to orchestrator streams
            enqueued: List[Dict[str, Any]] = []
            for item in decision.tasks:
                stream = item["stream"]
                payload = item["payload"]
                payload["context_depth"] = decision.context_depth
                
                # Create typed envelope
                task_id = f"task_{uuid.uuid4()}"
                # Destination should be the orchestrator segment (enforces vertical-only comms)
                stream_parts = stream.split(":")
                destination = stream_parts[2] if len(stream_parts) >= 3 else "unknown"

                envelope = create_task_envelope(
                    source="manager_agent",
                    task_id=task_id,
                    payload=payload,
                    destination=destination,
                    tenant_id=self.tenant_id,
                    intent=intent,
                    debug=({"llm_summary": llm_debug_summary} if llm_debug_summary else None),
                )
                
                try:
                    stream_id = self.redis.xadd(
                        stream,
                        to_redis_fields(envelope)
                    )
                    enqueued.append({
                        "stream": stream,
                        "id": stream_id.decode() if isinstance(stream_id, bytes) else stream_id,
                        "task_id": task_id
                    })
                    _trace_log(
                        "manager",
                        correlation_id=corr_id,
                        task_id=task_id,
                        step="delegated",
                        detail="manager_enqueue_orchestrator",
                        stream=stream,
                        orchestrator=destination,
                    )
                except Exception as e:
                    logger.error(f"Failed to enqueue to {stream}: {e}")

            # Optional chaining: if deep context and outreach is planned, wait for leads result then enqueue outbound.
            # Optional chaining: for inbound email reply flows, wait for Leads to produce a reply_packet
            # and then enqueue Outbound with that packet (so Outbound can deterministically delegate
            # to Copywriter without guessing).
            try:
                should_chain_reply = False
                if decision.context_depth == "deep" and "leads" in decision.orchestrators:
                    payload = req.payload if isinstance(req.payload, dict) else {}
                    ctx = payload.get("context") if isinstance(payload.get("context"), dict) else {}
                    email_event = ctx.get("email_event")
                    actions_allowed = ctx.get("actions_allowed") if isinstance(ctx.get("actions_allowed"), list) else []
                    reply_allowed = "reply" in [str(x).lower() for x in actions_allowed]
                    has_email = isinstance(email_event, dict) and bool(email_event)
                    should_chain_reply = has_email and reply_allowed

                if should_chain_reply:
                    self._chain_leads_to_outbound(enqueued, decision, start_time, correlation_id=corr_id)
            except Exception as chain_exc:
                logger.warning(f"Chaining leads→outbound failed: {chain_exc}")

            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            
            # Log decision with observability
            obs.log_decision(
                path="deterministic_pipeline",
                intent=decision.intent,
                confidence=decision.confidence,
                orchestrators=decision.orchestrators,
                used_fallback=decision.used_fallback,
                reasons=decision.reasons,
            )
            
            # Track cost (estimate based on LLM usage)
            estimated_cost = 0.0002 if "llm" in str(decision.reasons) else 0.0
            obs.track_cost(estimated_cost)
            
            return {
                "success": True,
                "execution_id": execution_id,
                "path": "deterministic_pipeline",
                "intent": decision.intent,
                "confidence": decision.confidence,
                "context_depth": decision.context_depth,
                "orchestrators": decision.orchestrators,
                "reasons": decision.reasons,
                "used_fallback": decision.used_fallback,
                "enqueued": enqueued,
                "latency_ms": elapsed,
                "timestamp": start_time.isoformat(),
            }
        except Exception as e:
            logger.error(f"Deterministic pipeline failed, considering deep agent fallback: {e}")
            # Step 3: Fallback to deep agent if enabled
            if self.enable_deep_agent and self.agent is not None:
                try:
                    messages = [("user", goal)]
                    if context:
                        context_str = json.dumps(context)
                        messages.insert(0, ("system", f"Additional context: {context_str}"))
                    agent_result = self.agent.invoke({"messages": messages})
                    elapsed = (datetime.now() - start_time).total_seconds() * 1000

                    # Log deep agent fallback (output suppressed to honor delegation-only contract)
                    obs.log_decision(
                        path="deep_agent_fallback",
                        model=self.model_name,
                    )
                    obs.track_cost(0.003)  # Estimate for gpt-4o-mini deep agent

                    return {
                        "success": True,
                        "execution_id": execution_id,
                        "path": "deep_agent_fallback",
                        "result": {
                            "status": "ran",
                            "message": "Deep agent fallback executed; output suppressed to keep manager delegation-only.",
                        },
                        "latency_ms": elapsed,
                        "timestamp": start_time.isoformat(),
                    }
                except Exception as e2:
                    elapsed = (datetime.now() - start_time).total_seconds() * 1000
                    return {
                        "success": False,
                        "execution_id": execution_id,
                        "path": "deep_agent_fallback",
                        "error": str(e2),
                        "latency_ms": elapsed,
                        "timestamp": start_time.isoformat(),
                    }
            # If deep agent not enabled, return failure
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            return {
                "success": False,
                "execution_id": execution_id,
                "path": "deterministic_pipeline",
                "intent": "unknown",
                "confidence": 0.0,
                "orchestrators": [],
                "reasons": ["error:deterministic_pipeline_exception"],
                "used_fallback": True,
                "enqueued": [],
                "error": str(e),
                "latency_ms": elapsed,
                "timestamp": start_time.isoformat(),
            }
    
    def get_task_result(self, task_id: str) -> Dict[str, Any]:
        """
        Get result of delegated task.
        
        Args:
            task_id: Task identifier from delegation
            
        Returns:
            Task status and result
        """
        return self.delegation.check_task_status(task_id)
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on Manager Agent.
        
        Returns:
            Health status including middleware components
        """
        health = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "model": self.model_name,
            "tenant_id": self.tenant_id,
            "components": {}
        }
        
        # Check Redis
        try:
            self.redis.ping()
            health["components"]["redis"] = {
                "status": "healthy",
                "tenant": self.tenant_id,
            }
        except Exception as e:
            health["components"]["redis"] = {
                "status": "unhealthy",
                "error": str(e),
            }
            health["status"] = "degraded"
        
        # Check Deep Agent Middleware
        if self.agent is not None:
            try:
                # Lazy import to avoid heavy deps unless enabled
                from .deep_agent_factory import get_middleware_status
                middleware_status = get_middleware_status(self.agent)
                health["components"]["middleware"] = {
                    "status": "healthy",
                    **middleware_status,
                }
            except Exception as e:
                health["components"]["middleware"] = {
                    "status": "unhealthy",
                    "error": str(e),
                }
                health["status"] = "degraded"
        else:
            health["components"]["middleware"] = {
                "status": "disabled",
            }
        
        # Check shortcuts
        try:
            shortcut_test = self.shortcuts.execute_shortcut("What is 1 + 1?")
            if shortcut_test["success"]:
                health["components"]["shortcuts"] = {
                    "status": "healthy",
                    "count": len(self.shortcuts.shortcuts),
                }
            else:
                health["components"]["shortcuts"] = {
                    "status": "degraded",
                    "count": len(self.shortcuts.shortcuts),
                }
        except Exception as e:
            health["components"]["shortcuts"] = {
                "status": "unhealthy",
                "error": str(e),
            }
            health["status"] = "degraded"
        
        # Check delegation tools
        health["components"]["delegation"] = {
            "status": "healthy",
            "orchestrators": ["control", "leads", "outbound", "coding", "data", "api"],
            "stream_namespace": f"{self.tenant_id}:orchestrators:<name>:tasks",
        }
        
        return health

    def _chain_leads_to_outbound(
        self,
        enqueued: List[Dict[str, Any]],
        decision: ManagerDecision,
        start_time: datetime,
        correlation_id: Optional[str] = None,
    ) -> None:
        """Best-effort chaining: wait for leads result and then enqueue outbound with reply packet."""

        corr = correlation_id or getattr(decision, "correlation_id", None) or getattr(decision, "task_id", None)
        leads_task_ids = [e.get("task_id") for e in enqueued if ":orchestrators:leads:" in e.get("stream", "")]
        if not leads_task_ids:
            return

        # Leads may call downstream agents (RAG/persistence/copywriter) and can exceed 20s
        # in real deployments. Use a higher default while still allowing env override.
        # Keep below the harness timeout (60s in development) to avoid killing the manager task.
        timeout_ms = int(os.getenv("MANAGER_CHAIN_LEADS_OUTBOUND_TIMEOUT_MS", "45000"))
        result_stream = f"{self.tenant_id}:orchestrators:leads:results"
        deadline = time.time() + max(1, timeout_ms / 1000)
        reply_packet = None
        result_env = None

        while time.time() < deadline:
            try:
                entries = self.redis.xrevrange(result_stream, max="+", min="-", count=50)
                for _msg_id, fields in entries:
                    env = from_redis_message(fields)
                    if env.metadata.task_id in leads_task_ids:
                        result_env = env
                        payload = env.payload or {}
                        reply_packet = payload.get("reply_packet") or payload.get("reply_packet_json")
                        break
                if reply_packet is not None:
                    break
            except Exception:
                pass
            time.sleep(0.2)

        if reply_packet is None:
            _trace_log(
                "manager",
                correlation_id=corr or "unknown",
                task_id=";".join(leads_task_ids),
                step="timeout",
                detail="chain_leads_to_outbound_no_reply_packet",
                result_stream=result_stream,
            )
            return

        outbound_stream = f"{self.tenant_id}:orchestrators:outbound:tasks"
        task_id = f"task_{uuid.uuid4()}"
        envelope = create_task_envelope(
            source="manager_agent",
            task_id=task_id,
            payload={
                "tenant_id": self.tenant_id,
                "source": "manager",
                "intent": decision.intent,
                "payload": {
                    "reply_packet": reply_packet,
                    "context_depth": decision.context_depth,
                    "upstream": {
                        "leads_task_ids": leads_task_ids,
                        "leads_result": result_env.payload if result_env else None,
                    },
                },
            },
            destination="outbound",
            tenant_id=self.tenant_id,
            intent=decision.intent,
        )
        try:
            stream_id = self.redis.xadd(outbound_stream, to_redis_fields(envelope))
            enqueued.append({
                "stream": outbound_stream,
                "id": stream_id.decode() if isinstance(stream_id, bytes) else stream_id,
                "task_id": task_id,
                "chained_from": leads_task_ids,
            })
            _trace_log(
                "manager",
                correlation_id=corr or "unknown",
                task_id=task_id,
                step="delegated",
                detail="manager_chain_leads_to_outbound",
                stream=outbound_stream,
                chained_from=leads_task_ids,
            )
        except Exception as e:
            logger.error(f"Failed to enqueue chained outbound task: {e}")


# Example usage
if __name__ == "__main__":
    import redis
    
    # Initialize Redis
    redis_client = redis.Redis(host='localhost', port=6379, decode_responses=False)
    
    # Create Manager Agent
    manager = ManagerAgent(redis_client, tenant_id="demo")
    
    # Test 1: Shortcut (calculation)
    print("Test 1: Shortcut calculation")
    result = manager.execute("What is 2 + 2?")
    print(f"Result: {result}\n")
    
    # Test 2: Data query delegation
    print("Test 2: Data query delegation")
    result = manager.execute("Find all leads in the tech industry created in the last 30 days")
    print(f"Result: {result}\n")
    
    # Test 3: Email generation delegation
    print("Test 3: Email generation")
    result = manager.execute("Generate an outreach email for lead_123 in campaign_456")
    print(f"Result: {result}\n")
    
    # Test 4: Health check
    print("Test 4: Health check")
    health = manager.health_check()
    print(f"Health: {health}\n")
