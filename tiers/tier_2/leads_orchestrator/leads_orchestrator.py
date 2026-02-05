"""
Leads Orchestrator - Tier 2 Deep Agent for Database Operations

This orchestrator acts as a middle-tier manager for all lead database operations.
It uses Deep Agents for strategic planning and delegates to:
- Deterministic tools (simple operations)
- Subagents (complex operations like RAG, Persistence)

Architecture:
- Layer 2: Deep Agent with TodoList, Filesystem, SubAgent middleware
- Layer 1: Wrapped in Agent Harness for production reliability
"""

import json
import uuid
import logging
import time
import hashlib
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from pathlib import Path
import os

import redis
from langchain.tools import tool
from deepagents import create_deep_agent
from core.envelope import task as create_task_envelope, to_redis_fields
from core.streams import assert_agents_stream
from core.envelope import from_redis_message
from core.schemas.reply_packet import ReplyPacket, LeadResolution, ConversationSummary, Facts, ActionsTaken, NextStep

# Lead qualification scoring
try:
    from tiers.tier_2.leads_orchestrator.qualification import QualificationScorer, score_lead_sync
    QUALIFICATION_ENABLED = True
except ImportError:
    QUALIFICATION_ENABLED = False
    QualificationScorer = None
    score_lead_sync = None

from tiers.tier_2.leads_orchestrator.qualification.lifecycle import (
    build_message_qualification_metadata,
    build_promotion_task_payload,
    build_staging_qualification_update,
    normalize_qualification_status,
)
from core.security.prompt_hardening import get_hardened_internal_prompt

logger = logging.getLogger(__name__)

# Lightweight structured trace logging for observability without extra streams.
def _trace_log(actor: str, *, correlation_id: str, task_id: str, step: str, detail: str, **kwargs: Any) -> None:
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
        # Trace logging must never break the main flow.
        pass


def _deterministic_message_id(
    sender: str,
    recipient: str,
    thread_id: str,
    subject: str,
    sent_at: str,
    body: str,
) -> str:
    """Generate a stable hash-based message id when none is provided.

    Includes a timestamp component so repeated interactions (separate inbound emails)
    do not collide when sender/recipient/thread/subject/body are identical.
    """
    raw = f"{sender}|{recipient}|{thread_id}|{subject}|{sent_at}|{body}".encode("utf-8", errors="ignore")
    return "hash_" + hashlib.sha256(raw).hexdigest()


def _deterministic_uuid5(*parts: str) -> str:
    """Generate a stable UUID for idempotent upserts."""
    name = "|".join([p for p in parts if p is not None])
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, name))


class LeadsOrchestrator:
    """
    Tier 2: Leads Database Orchestrator (Deep Agent)
    
    Responsibilities:
    - Coordinate ALL database-facing lead operations
    - Delegate to deterministic tools (simple operations)
    - Delegate to subagents (complex operations)
    - Use TodoListMiddleware for multi-step workflows
    - Use FilesystemMiddleware for large datasets
    
    Tools vs Subagents:
    - Tools: Deterministic operations (validate, write, query, update)
    - Subagents: Complex operations requiring AI (RAG enrichment, deduplication)
    """
    
    def __init__(
        self,
        redis_client: redis.Redis,
        tenant_id: str = "default",
        model: str = "gpt-4o-mini",
    ):
        """
        Initialize Leads Orchestrator with Deep Agent.

        Args:
            redis_client: Redis client for task delegation
            tenant_id: Tenant context for multi-tenant isolation
            model: OpenAI model (gpt-4o-mini for cost efficiency)
        """
        self.redis = redis_client
        self.tenant_id = tenant_id
        self.model = model

        # Create Deep Agent with middleware
        self.agent = create_deep_agent(
            model=model,
            system_prompt=self._get_system_prompt(),
            tools=self._build_tools(),
        )
        # TodoListMiddleware, FilesystemMiddleware, SubAgentMiddleware auto-configured

        logger.info(f"LeadsOrchestrator initialized (tenant={tenant_id}, model={model})")

    def _get_system_prompt(self) -> str:
        """System prompt defining Leads Orchestrator role and decision framework"""
        base_prompt = f"""You are the Leads Orchestrator - a Tier 2 autonomous agent in a 3-tier event-driven system.

## SYSTEM ARCHITECTURE
- **Tier 1 (Manager):** Assigns you goals via Redis Streams. You report results back.
- **Tier 2 (You):** Autonomous orchestrator for lead operations. You plan, execute, and complete tasks independently.
- **Tier 3 (Agents):** Specialist workers you delegate to: RAG (enrichment), Persistence (database), Deduplication.

## COMMUNICATION RULES (HARD CONSTRAINT)
- **Vertical only:** You may communicate UPWARD to Tier 1 (via your result payload) and DOWNWARD to Tier 3 agents (via your delegation tools).
- **No horizontal comms:** You MUST NOT coordinate with other Tier 2 orchestrators directly.
- **Stream naming** (do not invent new patterns):
    - Manager: `{self.tenant_id}:manager:tasks` → `{self.tenant_id}:manager:results`
    - Orchestrators: `{self.tenant_id}:orchestrators:leads:tasks` → `{self.tenant_id}:orchestrators:leads:results`
    - Agents: `{self.tenant_id}:agents:<agent_name>:tasks` → `{self.tenant_id}:agents:<agent_name>:results`

## YOUR IDENTITY
You are an AUTONOMOUS EXECUTOR, not an assistant. You:
- NEVER ask for permission or confirmation
- NEVER say "Would you like me to..." or "Should I..."
- ALWAYS take action immediately based on the goal
- ALWAYS complete the full task before returning results

## YOUR TOOLS

**Database Operations (execute directly):**
- `query_leads_tool(filters, limit)` - Search leads by any field (email, stage, industry, etc.)
- `write_lead_tool(lead_data)` - Create a new lead record
- `read_lead_tool(lead_id)` - Fetch a single lead by ID
- `update_lead_tool(lead_id, updates)` - Modify lead fields
- `validate_lead_tool(lead_data)` - Check data quality (email format, required fields)
- `move_lead_stage_tool(lead_id, to_stage)` - Update pipeline stage

**Tier 3 Delegation (for complex operations):**
- `delegate_to_rag_agent_tool(query, context)` - Enrich leads with external data, semantic search
- `delegate_to_rag_context_tool(email, lead_id, conversation_limit, message_limit)` - Retrieve lead + conversation context
- `delegate_to_persistence_agent_tool(operation, data)` - Bulk writes, complex queries
- `compound_persistence_tool(steps, continue_on_skip, rollback_on_failure)` - Multi-step FK-safe writes with $ref chaining
- `store_inbound_email_tool(email_event, lead_data, cleanup_staging)` - Standard inbound email compound flow
- `delegate_to_deduplication_agent_tool(lead_ids)` - Find and merge duplicate leads

## EXECUTION PATTERN
1. **Analyze:** Parse the goal and context. What data do you have? What is the desired outcome?
2. **Plan:** Determine the minimal steps needed. For simple tasks, skip planning and execute.
3. **Execute:** Call tools immediately. Do NOT describe what you will do - just do it.
4. **Iterate:** If a query returns no results, try broader filters or alternative approaches.
5. **Complete:** Return a structured result with what was accomplished, data retrieved or written, issues encountered, and next recommended actions (if any).

## OUTPUT REQUIREMENTS
- Prefer returning a JSON object in your final response.
- Do not ask the user questions. If multiple sensible next actions exist, choose one and proceed; include a `next_actions` list for downstream systems.

## CONSTRAINTS
- Tenant isolation: All operations are scoped to tenant `{self.tenant_id}`
- No external API calls - delegate to RAG agent for external data
- Return JSON-structured results when possible

You receive tasks from Manager (Tier 1). Execute autonomously and return results. Never wait for approval."""
        return get_hardened_internal_prompt(base_prompt)

    def _build_tools(self) -> List:
        """Build all tools (deterministic + delegation)"""
        return [
            # Deterministic tools (simple operations)
            self._create_validate_lead_tool(),
            self._create_write_lead_tool(),
            self._create_read_lead_tool(),
            self._create_update_lead_tool(),
            self._create_query_leads_tool(),
            self._create_query_conversations_tool(),
            self._create_query_messages_tool(),
            self._create_move_lead_stage_tool(),
            
            # Subagent delegation tools (complex operations)
            self._create_delegate_to_rag_agent_tool(),
            self._create_delegate_to_rag_context_tool(),
            self._create_delegate_to_persistence_agent_tool(),
            self._create_compound_persistence_tool(),
            self._create_store_inbound_email_tool(),
            self._create_delegate_to_deduplication_agent_tool(),
        ]
    
    # ==================== DETERMINISTIC TOOLS ====================
    
    def _create_validate_lead_tool(self):
        """Tool for validating lead data quality"""
        
        @tool
        def validate_lead_tool(lead_data: Optional[dict] = None) -> dict:
            """
            Validate lead data quality (email format, required fields).
            
            This is a DETERMINISTIC operation - no AI reasoning needed.
            
            Args:
                lead_data: Lead fields to validate (email, first_name, last_name, etc.)
            
            Returns:
                {"valid": bool, "errors": list, "warnings": list}
            """
            lead_data = lead_data if isinstance(lead_data, dict) else {}
            errors = []
            warnings = []
            
            # Required fields check
            required = ["email", "first_name", "last_name"]
            for field in required:
                if field not in lead_data or not lead_data.get(field):
                    errors.append(f"Missing required field: {field}")
            
            # Email format validation
            import re
            if "email" in lead_data:
                email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                if not re.match(email_regex, lead_data["email"]):
                    errors.append(f"Invalid email format: {lead_data['email']}")
            
            # Optional field warnings
            optional_fields = ["company", "phone", "industry"]
            for field in optional_fields:
                if field not in lead_data or not lead_data.get(field):
                    warnings.append(f"Missing optional field: {field} (enrichment recommended)")
            
            result = {
                "valid": len(errors) == 0,
                "errors": errors,
                "warnings": warnings,
                "checked_at": datetime.utcnow().isoformat()
            }
            
            logger.info(f"Validated lead: valid={result['valid']}, errors={len(errors)}")
            return result
        
        return validate_lead_tool
    
    def _create_write_lead_tool(self):
        """Tool for writing a single lead to database"""
        
        @tool
        def write_lead_tool(lead_data: dict, wait_for_result: Optional[bool] = None) -> dict:
            """
            Write a single lead to database.
            
            This is a DETERMINISTIC operation - no AI reasoning needed.
            For bulk operations (> 100 leads), use delegate_to_persistence_agent_tool instead.
            
            Args:
                lead_data: Lead fields (email, first_name, last_name, company, etc.)
            
            Returns:
                {"lead_id": str, "status": str, "created_at": str}
            """
            enqueue = self._enqueue_persistence_write_lead(lead_data)
            if wait_for_result is None:
                wait_for_result = os.getenv("LEADS_WAIT_FOR_PERSISTENCE_RESULTS", "0").lower() in ("1", "true", "yes")

            if wait_for_result:
                payload = self._wait_for_agent_result(
                    result_stream=f"{self.tenant_id}:agents:persistence:results",
                    task_id=enqueue.get("persistence_task_id", ""),
                    timeout_s=int(os.getenv("LEADS_PERSISTENCE_WAIT_TIMEOUT_S", "30")),
                )
                if isinstance(payload, dict) and payload.get("status") == "success":
                    enqueue["persistence_result"] = payload.get("result")
                    enqueue["persistence_status"] = "success"
                else:
                    enqueue["persistence_status"] = "timeout"

            return enqueue
        
        return write_lead_tool

    def _create_read_lead_tool(self):
        """Tool for reading a lead by id via Persistence Agent"""

        @tool
        def read_lead_tool(lead_id: str, wait_for_result: Optional[bool] = None) -> dict:
            """Read a single lead record by lead_id.

            This is a DETERMINISTIC operation - no AI reasoning needed.

            Args:
                lead_id: Lead id (string)

            Returns:
                {"lead_id": str, "status": str, "persistence_task_id": str}
            """
            enqueue = self._enqueue_persistence_read_lead(lead_id)
            if wait_for_result is None:
                wait_for_result = os.getenv("LEADS_WAIT_FOR_PERSISTENCE_RESULTS", "0").lower() in ("1", "true", "yes")

            if wait_for_result:
                payload = self._wait_for_agent_result(
                    result_stream=f"{self.tenant_id}:agents:persistence:results",
                    task_id=enqueue.get("persistence_task_id", ""),
                    timeout_s=int(os.getenv("LEADS_PERSISTENCE_WAIT_TIMEOUT_S", "30")),
                )
                if isinstance(payload, dict) and payload.get("status") == "success":
                    enqueue["persistence_result"] = payload.get("result")
                    enqueue["persistence_status"] = "success"
                else:
                    enqueue["persistence_status"] = "timeout"

            return enqueue

        return read_lead_tool

    def _enqueue_persistence_write_lead(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        lead_id = str(lead_data.get("id") or f"lead_{uuid.uuid4()}")
        task_id = f"persist_write_{uuid.uuid4()}"

        payload = {
            "operation": "write",
            "table": "leads",
            "record": {**lead_data, "id": lead_id},
            "delegated_by": "leads_orchestrator",
            "timestamp": datetime.utcnow().isoformat(),
        }
        stream_name = f"{self.tenant_id}:agents:persistence:tasks"
        assert_agents_stream(stream_name)

        envelope = create_task_envelope(
            source="leads_orchestrator",
            task_id=task_id,
            payload=payload,
            destination="persistence_agent",
            tenant_id=self.tenant_id,
        )

        try:
            self.redis.xadd(stream_name, to_redis_fields(envelope))
            logger.info(
                f"Delegated lead write to PersistenceAgent stream={stream_name} task_id={task_id}"
            )
        except Exception as e:
            logger.error(f"Failed to enqueue persistence write: {e}")

        return {
            "lead_id": lead_id,
            "status": "enqueued_for_persistence",
            "created_at": datetime.utcnow().isoformat(),
            "tenant_id": self.tenant_id,
            "persistence_task_id": task_id,
        }

    def _enqueue_persistence_read_lead(self, lead_id: str) -> Dict[str, Any]:
        task_id = f"persist_read_{uuid.uuid4()}"
        payload = {
            "operation": "read",
            "table": "leads",
            "id_value": lead_id,
            "id_column": "id",
            "delegated_by": "leads_orchestrator",
            "timestamp": datetime.utcnow().isoformat(),
        }
        stream_name = f"{self.tenant_id}:agents:persistence:tasks"
        assert_agents_stream(stream_name)

        envelope = create_task_envelope(
            source="leads_orchestrator",
            task_id=task_id,
            payload=payload,
            destination="persistence_agent",
            tenant_id=self.tenant_id,
        )

        try:
            self.redis.xadd(stream_name, to_redis_fields(envelope))
            logger.info(
                f"Delegated lead read to PersistenceAgent stream={stream_name} task_id={task_id}"
            )
        except Exception as e:
            logger.error(f"Failed to enqueue persistence read: {e}")

        return {
            "lead_id": lead_id,
            "status": "enqueued_for_persistence",
            "requested_at": datetime.utcnow().isoformat(),
            "tenant_id": self.tenant_id,
            "persistence_task_id": task_id,
        }

    def _enqueue_persistence_query_leads(self, filters: Dict[str, Any], limit: int = 100) -> Dict[str, Any]:
        task_id = f"persist_query_{uuid.uuid4()}"
        payload = {
            "operation": "query",
            "table": "leads",
            "filters": filters,
            "limit": min(int(limit), 10000),
            "order_by": None,
            "descending": False,
            "delegated_by": "leads_orchestrator",
            "timestamp": datetime.utcnow().isoformat(),
        }
        stream_name = f"{self.tenant_id}:agents:persistence:tasks"
        assert_agents_stream(stream_name)

        envelope = create_task_envelope(
            source="leads_orchestrator",
            task_id=task_id,
            payload=payload,
            destination="persistence_agent",
            tenant_id=self.tenant_id,
        )

        try:
            self.redis.xadd(stream_name, to_redis_fields(envelope))
            logger.info(
                f"Delegated lead query to PersistenceAgent stream={stream_name} task_id={task_id}"
            )
        except Exception as e:
            logger.error(f"Failed to enqueue persistence query: {e}")

        return {
            "status": "enqueued_for_persistence",
            "tenant_id": self.tenant_id,
            "filters": filters,
            "limit": limit,
            "persistence_task_id": task_id,
        }

    def _enqueue_persistence_compound(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Enqueue a compound persistence operation (multi-step create/update/upsert/delete)."""
        task_id = f"persist_compound_{uuid.uuid4()}"
        compound_payload = {
            "operation": "compound",
            **payload,
            "delegated_by": payload.get("delegated_by", "leads_orchestrator"),
            "timestamp": datetime.utcnow().isoformat(),
        }

        stream_name = f"{self.tenant_id}:agents:persistence:tasks"
        assert_agents_stream(stream_name)

        envelope = create_task_envelope(
            source="leads_orchestrator",
            task_id=task_id,
            payload=compound_payload,
            destination="persistence_agent",
            tenant_id=self.tenant_id,
        )

        try:
            self.redis.xadd(stream_name, to_redis_fields(envelope))
            logger.info(
                f"Delegated compound persistence to PersistenceAgent stream={stream_name} task_id={task_id}"
            )
        except Exception as e:
            logger.error(f"Failed to enqueue compound persistence: {e}")

        return {
            "status": "enqueued_for_persistence",
            "tenant_id": self.tenant_id,
            "persistence_task_id": task_id,
            "operation": "compound",
        }

    def _enqueue_persistence_promote_staging_lead(
        self,
        *,
        staging_lead_id: str,
        lead_score: int = 50,
        campaign_id: Optional[str] = None,
        qualification_status: str = "qualified",
    ) -> Dict[str, Any]:
        """Enqueue promotion of a staging lead to the leads table (copy conversations/messages)."""
        task_id = f"promote_staging_{uuid.uuid4()}"
        payload = {
            "operation": "promote_staging_lead",
            "staging_lead_id": staging_lead_id,
            "lead_score": int(lead_score) if isinstance(lead_score, int) or str(lead_score).isdigit() else 50,
            "campaign_id": campaign_id,
            "qualification_status": qualification_status,
            "delegated_by": "leads_orchestrator",
            "timestamp": datetime.utcnow().isoformat(),
        }

        stream_name = f"{self.tenant_id}:agents:persistence:tasks"
        assert_agents_stream(stream_name)

        envelope = create_task_envelope(
            source="leads_orchestrator",
            task_id=task_id,
            payload=payload,
            destination="persistence_agent",
            tenant_id=self.tenant_id,
        )

        try:
            self.redis.xadd(stream_name, to_redis_fields(envelope))
            logger.info(
                "Delegated staging promotion to PersistenceAgent stream=%s task_id=%s",
                stream_name,
                task_id,
            )
        except Exception as e:
            logger.error(f"Failed to enqueue staging promotion: {e}")

        return {
            "status": "enqueued_for_persistence",
            "tenant_id": self.tenant_id,
            "persistence_task_id": task_id,
            "operation": "promote_staging_lead",
        }

    def _build_inbound_email_steps(
        self,
        *,
        email_event: Dict[str, Any],
        lead_data: Dict[str, Any],
        cleanup_staging: bool,
        lead_resolution: Optional[Dict[str, Any]] = None,
        email_classification: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """Construct FK-safe steps for storing inbound email.

        Routing rules:
        - If an existing lead is found (exact email or domain match), attach the conversation/message to `leads`.
        - If an existing staging lead is found, write to staging tables.
        - Otherwise, create a staging_lead and attach the inbound conversation/message there.
        
        Qualification (when enabled):
        - Fast-track: High-score new leads skip staging and write directly to leads table
        - Auto-promote: Qualifying staging leads get a promotion step appended
        """

        sender_email = (email_event or {}).get("from") or ""
        recipient_email = (email_event or {}).get("to") or ""
        thread_id = (email_event or {}).get("thread_id")
        subject = (email_event or {}).get("subject", "")
        message_id = (email_event or {}).get("message_id")
        body = (email_event or {}).get("body", "")
        metadata = (email_event or {}).get("metadata", {})
        sent_at = (email_event or {}).get("received_at") or (email_event or {}).get("sent_at") or datetime.utcnow().isoformat()

        if not message_id:
            message_id = _deterministic_message_id(
                sender_email,
                recipient_email,
                thread_id or "",
                subject or "",
                str(sent_at or ""),
                body or "",
            )
        archived_at = datetime.utcnow().isoformat()

        lr = lead_resolution or {}
        resolved_source = lr.get("lead_source") or lr.get("source")
        resolved_lead_id = lr.get("lead_id") or lr.get("id")

        target = "staging_new"
        if resolved_source == "leads" and resolved_lead_id:
            target = "lead_existing"
        elif resolved_source == "staging_leads" and resolved_lead_id:
            target = "staging_existing"

        # =====================================================================
        # QUALIFICATION SCORING - Fast-track & Auto-promote Logic
        # =====================================================================
        qualification_result = None
        qualification_enabled = QUALIFICATION_ENABLED and os.getenv("LEADS_QUALIFICATION_ENABLED", "1").lower() in ("1", "true", "yes")
        
        if qualification_enabled and score_lead_sync is not None:
            try:
                # Build lead profile from available data
                lead_profile = {
                    "email": sender_email,
                    **lead_data,
                }
                
                # Add conversation context if available
                conv_history = conversation_history or []
                if body and not conv_history:
                    # Use current email as conversation history
                    conv_history = [{"content": body, "direction": "inbound", "sender": sender_email}]
                
                # Determine lead source for scoring
                score_lead_source = "new" if target == "staging_new" else (
                    "leads" if target == "lead_existing" else "staging_leads"
                )
                
                qualification_result = score_lead_sync(
                    lead_data=lead_profile,
                    conversation_history=conv_history,
                    email_classification=email_classification or {},
                    lead_source=score_lead_source,
                    email_direction="inbound",
                )
                
                logger.info(
                    "[QUALIFICATION] email=%s score=%d decision=%s fast_track=%s signals=%s",
                    sender_email,
                    qualification_result.score,
                    qualification_result.decision,
                    qualification_result.fast_track,
                    qualification_result.signals[:5],  # Log first 5 signals
                )
                
                # FAST-TRACK: High-score new lead → write directly to leads table
                if target == "staging_new" and qualification_result.fast_track:
                    target = "lead_fast_track"
                    logger.info(
                        "[QUALIFICATION] Fast-tracking new lead to leads table: email=%s score=%d",
                        sender_email,
                        qualification_result.score,
                    )
                    
            except Exception as e:
                logger.warning(f"[QUALIFICATION] Scoring failed, falling back to default routing: {e}")
                qualification_result = None

        steps: List[Dict[str, Any]] = []
        promotion_candidate: Optional[Dict[str, Any]] = None

        # =====================================================================
        # FAST-TRACK PATH: New lead with high score → write directly to leads
        # =====================================================================
        if target == "lead_fast_track":
            # Generate new lead ID for fast-tracked lead
            fast_track_lead_id = _deterministic_uuid5(
                self.tenant_id,
                "lead",
                sender_email,
            )
            conversation_pk = _deterministic_uuid5(
                self.tenant_id,
                "conversation",
                fast_track_lead_id,
                str(thread_id or subject or ""),
            )
            message_pk = _deterministic_uuid5(
                self.tenant_id,
                "message",
                conversation_pk,
                str(message_id or ""),
            )
            
            message_metadata: Dict[str, Any] = {}
            if isinstance(metadata, dict):
                message_metadata.update(metadata)
            if message_id:
                message_metadata.setdefault("message_id", message_id)
            if thread_id:
                message_metadata.setdefault("thread_id", thread_id)
            if subject:
                message_metadata.setdefault("subject", subject)
            if sender_email:
                message_metadata.setdefault("from", sender_email)
            if recipient_email:
                message_metadata.setdefault("to", recipient_email)
            
            # Add qualification metadata
            if qualification_result:
                message_metadata["qualification"] = build_message_qualification_metadata(
                    decision=getattr(qualification_result, "decision", None),
                    score=getattr(qualification_result, "score", None),
                    signals=getattr(qualification_result, "signals", None),
                    fast_track=True,
                )
            
            steps.extend([
                {
                    "step_name": "lead",
                    "table": "leads",
                    "operation": "upsert",
                    "data": {
                        "id": fast_track_lead_id,
                        "email": sender_email,
                        "source": "inbound_email",
                        "lead_score": qualification_result.score if qualification_result else 85,
                        "qualification_status": normalize_qualification_status(
                            getattr(qualification_result, "decision", None)
                        ),
                        "current_status": "active",
                        **lead_data,
                    },
                    "match_on": ["id"],
                },
                {
                    "step_name": "conversation",
                    "table": "conversations",
                    "operation": "upsert",
                    "data": {
                        "id": conversation_pk,
                        "lead_id": "$ref:lead.id",
                        "thread_id": thread_id,
                        "subject": subject,
                        "channel": "email",
                        "status": "active",
                        "summary": subject or "",
                    },
                    "match_on": ["id"],
                },
                {
                    "step_name": "message",
                    "table": "messages",
                    "operation": "upsert",
                    "data": {
                        "id": message_pk,
                        "conversation_id": "$ref:conversation.id",
                        "sender_type": "lead",
                        "text_content": body,
                        "sent_at": sent_at,
                        "message_id": message_id,
                        "metadata": message_metadata,
                    },
                    "match_on": ["id"],
                },
            ])
            
            return steps

        if target == "lead_existing":
            conversation_pk = _deterministic_uuid5(
                self.tenant_id,
                "conversation",
                str(resolved_lead_id or ""),
                str(thread_id or subject or ""),
            )
            message_pk = _deterministic_uuid5(
                self.tenant_id,
                "message",
                conversation_pk,
                str(message_id or ""),
            )

            message_metadata: Dict[str, Any] = {}
            if isinstance(metadata, dict):
                message_metadata.update(metadata)
            # Preserve upstream identifiers for debugging/idempotency.
            if message_id:
                message_metadata.setdefault("message_id", message_id)
            if thread_id:
                message_metadata.setdefault("thread_id", thread_id)
            if subject:
                message_metadata.setdefault("subject", subject)
            if sender_email:
                message_metadata.setdefault("from", sender_email)
            if recipient_email:
                message_metadata.setdefault("to", recipient_email)

            steps.extend(
                [
                    {
                        "step_name": "lead",
                        "table": "leads",
                        "operation": "upsert",
                        "data": {"id": resolved_lead_id, "email": sender_email, **lead_data},
                        "match_on": ["id"],
                    },
                    {
                        "step_name": "conversation",
                        "table": "conversations",
                        "operation": "upsert",
                        "data": {
                            "id": conversation_pk,
                            "lead_id": "$ref:lead.id",
                            "thread_id": thread_id,
                            "subject": subject,
                            "channel": "email",
                            "status": "active",
                            "summary": subject or "",
                        },
                        # Use PK upsert to avoid relying on partial unique indexes.
                        "match_on": ["id"],
                    },
                    {
                        "step_name": "message",
                        "table": "messages",
                        "operation": "upsert",
                        "data": {
                            "id": message_pk,
                            "conversation_id": "$ref:conversation.id",
                            "sender_type": "lead",
                            "text_content": body,
                            "sent_at": sent_at,
                            "message_id": message_id,
                            "metadata": message_metadata or {},
                        },
                        # Use PK upsert to avoid relying on partial unique indexes.
                        "match_on": ["id"],
                    },
                    {
                        "step_name": "update_stage",
                        "table": "leads",
                        "operation": "update",
                        "where": {"id": "$ref:lead.id"},
                        "data": {"stage": "engaged"},
                        "on_error": "warn",
                    },
                ]
            )

            if cleanup_staging and sender_email:
                steps.append(
                    {
                        "step_name": "cleanup_staging",
                        "table": "staging_leads",
                        "operation": "update",
                        "where": {"email": sender_email},
                        "data": {"archived_at": archived_at},
                        "on_error": "skip",
                    }
                )

        elif target == "staging_existing":
            # Existing staging lead found - update it and add conversation/message
            staging_conversation_pk = _deterministic_uuid5(
                self.tenant_id,
                "staging_conversation",
                str(sender_email or ""),
                str(thread_id or subject or ""),
            )
            staging_message_pk = _deterministic_uuid5(
                self.tenant_id,
                "staging_message",
                staging_conversation_pk,
                str(message_id or ""),
            )
            steps.extend(
                [
                    {
                        "step_name": "staging_lead",
                        "table": "staging_leads",
                        "operation": "upsert",
                        "data": {"id": resolved_lead_id, "email": sender_email, "source": "inbound_email", **lead_data},
                        "match_on": ["id"],
                    },
                    {
                        "step_name": "staging_conversation",
                        "table": "staging_conversations",
                        "operation": "upsert",
                        "data": {
                            "id": staging_conversation_pk,
                            "staging_lead_id": "$ref:staging_lead.id",
                            "thread_id": thread_id,
                            "subject": subject,
                            "channel": "email",
                            "status": "open",
                            "metadata": {},
                        },
                        # Use PK upsert to avoid relying on partial unique indexes.
                        "match_on": ["id"],
                    },
                    {
                        "step_name": "staging_message",
                        "table": "staging_messages",
                        "operation": "upsert",
                        "data": {
                            "id": staging_message_pk,
                            "staging_conversation_id": "$ref:staging_conversation.id",
                            "sender": sender_email,
                            "receiver": recipient_email,
                            "content": body,
                            "sent_at": sent_at,
                            "message_id": message_id,
                            "direction": "inbound",  # From lead to us
                            "metadata": metadata or {},
                        },
                        # Use PK upsert to avoid relying on partial unique indexes.
                        "match_on": ["id"],
                    },
                ]
            )

        else:  # staging_new
            staging_lead_id = _deterministic_uuid5(
                self.tenant_id,
                "staging_lead",
                str(sender_email or ""),
            )
            staging_conversation_pk = _deterministic_uuid5(
                self.tenant_id,
                "staging_conversation",
                str(sender_email or ""),
                str(thread_id or subject or ""),
            )
            staging_message_pk = _deterministic_uuid5(
                self.tenant_id,
                "staging_message",
                staging_conversation_pk,
                str(message_id or ""),
            )
            # DEDUPLICATION RULES:
            # - staging_leads: match on (client_id, email) - client_id auto-injected by persistence agent
            # - staging_conversations: match on (staging_lead_id, thread_id) OR (staging_lead_id, subject)
            # - staging_messages: match on (staging_conversation_id, message_id)
            steps.extend(
                [
                    {
                        "step_name": "staging_lead",
                        "table": "staging_leads",
                        "operation": "upsert",
                        "data": {"id": staging_lead_id, "email": sender_email, "source": "inbound_email", **lead_data},
                        # Uses unique index: ux_staging_leads_client_email (client_id, email)
                        # client_id is auto-injected by persistence agent's _inject_scoping_fields
                        "match_on": ["client_id", "email"],
                    },
                    {
                        "step_name": "staging_conversation",
                        "table": "staging_conversations",
                        "operation": "upsert",
                        "data": {
                            "id": staging_conversation_pk,
                            "staging_lead_id": "$ref:staging_lead.id",
                            "thread_id": thread_id,
                            "subject": subject,
                            "channel": "email",
                            "status": "open",
                            "metadata": {},
                        },
                        # Use PK upsert to avoid relying on partial unique indexes.
                        "match_on": ["id"],
                    },
                    {
                        "step_name": "staging_message",
                        "table": "staging_messages",
                        "operation": "upsert",
                        "data": {
                            "id": staging_message_pk,
                            "staging_conversation_id": "$ref:staging_conversation.id",
                            "sender": sender_email,
                            "receiver": recipient_email,
                            "content": body,
                            "sent_at": sent_at,
                            "message_id": message_id,
                            "direction": "inbound",  # From lead to us
                            "metadata": metadata or {},
                        },
                        # Use PK upsert to avoid relying on partial unique indexes.
                        "match_on": ["id"],
                    },
                ]
            )

        # =====================================================================
        # AUTO-PROMOTION: If staging lead qualifies, mark for promotion
        # =====================================================================
        if qualification_result and qualification_result.promote and target in ("staging_existing", "staging_new"):
            # Add step to update staging lead with qualification score and mark promotion_ready
            staging_lead_ref = "$ref:staging_lead.id"
            steps.append(
                {
                    "step_name": "update_qualification",
                    "table": "staging_leads",
                    "operation": "update",
                    "where": {"id": staging_lead_ref},
                    "data": build_staging_qualification_update(
                        decision=getattr(qualification_result, "decision", None),
                        promote=True,
                        score=getattr(qualification_result, "score", None),
                    ),
                    "on_error": "warn",
                }
            )
            logger.info(
                "[QUALIFICATION] Marked staging lead for promotion: email=%s score=%d",
                sender_email,
                qualification_result.score,
            )

            staging_lead_id = resolved_lead_id
            if target == "staging_new":
                staging_lead_id = _deterministic_uuid5(
                    self.tenant_id,
                    "staging_lead",
                    str(sender_email or ""),
                )

            campaign_id = None
            if isinstance(lead_data, dict):
                campaign_id = lead_data.get("campaign_id")
            if not campaign_id and isinstance(lr, dict):
                lr_data = lr.get("lead_data") if isinstance(lr.get("lead_data"), dict) else {}
                campaign_id = lr_data.get("campaign_id")

            if staging_lead_id:
                promotion_candidate = {
                    "staging_lead_id": staging_lead_id,
                    "lead_score": qualification_result.score,
                    "campaign_id": campaign_id,
                    "qualification_status": normalize_qualification_status(
                        getattr(qualification_result, "decision", None)
                    ),
                }

        return steps, promotion_candidate

    def _enqueue_persistence_query_table(
        self,
        *,
        table: str,
        filters: Dict[str, Any],
        limit: int = 100,
        order_by: str | None = None,
        descending: bool = False,
        select: List[str] | None = None,
    ) -> Dict[str, Any]:
        """Generic PersistenceAgent query helper for non-leads tables (e.g., conversations/messages)."""
        task_id = f"persist_query_{uuid.uuid4()}"
        payload: Dict[str, Any] = {
            "operation": "query",
            "table": table,
            "filters": filters,
            "limit": min(int(limit), 10000),
            "order_by": order_by,
            "descending": bool(descending),
            "delegated_by": "leads_orchestrator",
            "timestamp": datetime.utcnow().isoformat(),
        }
        if isinstance(select, list) and select:
            payload["select"] = select

        stream_name = f"{self.tenant_id}:agents:persistence:tasks"
        assert_agents_stream(stream_name)

        envelope = create_task_envelope(
            source="leads_orchestrator",
            task_id=task_id,
            payload=payload,
            destination="persistence_agent",
            tenant_id=self.tenant_id,
        )

        try:
            self.redis.xadd(stream_name, to_redis_fields(envelope))
            logger.info(
                f"Delegated query table={table} to PersistenceAgent stream={stream_name} task_id={task_id}"
            )
        except Exception as e:
            logger.error(f"Failed to enqueue persistence query table={table}: {e}")

        return {
            "status": "enqueued_for_persistence",
            "tenant_id": self.tenant_id,
            "table": table,
            "filters": filters,
            "limit": limit,
            "persistence_task_id": task_id,
        }

    def _wait_for_agent_result(self, *, result_stream: str, task_id: str, timeout_s: int = 30) -> Optional[Dict[str, Any]]:
        """Best-effort synchronous wait for a specific task result.

        Implementation notes
        - Uses XREAD (blocking) starting from the current stream tail so we can't miss
          results due to high stream volume (which can happen with naive XREVRANGE(count=50)).
        - Falls back to best-effort behavior on Redis errors.
        """

        timeout_s = max(1, int(timeout_s))
        deadline = time.time() + timeout_s

        # Start reading from the stream tail so we only see new results.
        last_id = "$"
        try:
            info = self.redis.xinfo_stream(result_stream)
            if isinstance(info, dict) and info.get("last-generated-id"):
                last_id = info.get("last-generated-id")
        except Exception:
            # If we can't inspect the stream, still attempt a blocking read from "$".
            last_id = "$"

        while time.time() < deadline:
            try:
                remaining_ms = int(max(0, (deadline - time.time())) * 1000)
                block_ms = min(500, remaining_ms) if remaining_ms else 0

                # XREAD returns [(stream, [(id, fields), ...])]
                resp = self.redis.xread({result_stream: last_id}, count=100, block=block_ms)
                if not resp:
                    continue

                for _stream, messages in resp:
                    for msg_id, fields in messages:
                        last_id = msg_id
                        try:
                            env = from_redis_message(fields)
                        except Exception:
                            continue
                        if env.metadata.task_id == task_id:
                            return env.payload
            except Exception:
                # Avoid tight loop; keep best-effort semantics.
                time.sleep(0.5)
        return None
    
    def _create_update_lead_tool(self):
        """Tool for updating lead fields"""
        
        @tool
        def update_lead_tool(lead_id: str, updates: dict) -> dict:
            """
            Update an existing lead's fields.
            
            This is a DETERMINISTIC operation - no AI reasoning needed.
            
            Args:
                lead_id: Lead UUID
                updates: Fields to update ({"company": "New Corp", "stage": "qualified"})
            
            Returns:
                {"lead_id": str, "updated_fields": list, "status": str}
            """
            # TODO: Integrate with actual persistence layer
            # from agent.operational_agents.persistence_agent.facade import PersistenceFacade
            # facade = PersistenceFacade(self.tenant_id)
            # result = facade.update_lead(lead_id, updates)
            
            result = {
                "lead_id": lead_id,
                "updated_fields": list(updates.keys()),
                "status": "updated",
                "updated_at": datetime.utcnow().isoformat()
            }
            
            logger.info(f"Updated lead {lead_id}: {list(updates.keys())}")
            return result
        
        return update_lead_tool
    
    def _create_query_leads_tool(self):
        """Tool for querying leads with filters"""
        
        @tool
        def query_leads_tool(filters: Optional[dict] = None, limit: int = 100, wait_for_result: Optional[bool] = None) -> dict:
            """
            Query leads from database with filters.
            
            This is a DETERMINISTIC operation - no AI reasoning needed.
            For large result sets (> 1000), automatically uses Filesystem.
            
            Args:
                filters: Query filters ({"stage": "qualified", "company": "Tech Corp"})
                limit: Max results (default 100, max 10000)
            
            Returns:
                {"leads": list, "count": int} or {"filesystem_path": str, "count": int}
            """
            filters = filters if isinstance(filters, dict) else {}
            enqueue = self._enqueue_persistence_query_leads(filters, limit=limit)

            # Default behavior: non-blocking unless explicitly enabled via env for E2E.
            if wait_for_result is None:
                wait_for_result = os.getenv("LEADS_WAIT_FOR_PERSISTENCE_RESULTS", "0").lower() in ("1", "true", "yes")

            if wait_for_result:
                result_stream = f"{self.tenant_id}:agents:persistence:results"
                payload = self._wait_for_agent_result(
                    result_stream=result_stream,
                    task_id=enqueue.get("persistence_task_id", ""),
                    timeout_s=int(os.getenv("LEADS_PERSISTENCE_WAIT_TIMEOUT_S", "30")),
                )
                if isinstance(payload, dict) and payload.get("status") == "success":
                    leads = payload.get("result") or []
                    if not isinstance(leads, list):
                        leads = []
                else:
                    leads = []
            else:
                leads = []

            count = len(leads)
            
            # If large result set, store in filesystem
            if count > 1000:
                fs_path = f"./agent_context/{self.tenant_id}/leads_query_{uuid.uuid4()}.json"
                Path(fs_path).parent.mkdir(parents=True, exist_ok=True)
                with open(fs_path, 'w') as f:
                    json.dump(leads, f)
                
                result = {
                    "count": count,
                    "filesystem_path": fs_path,
                    "message": f"Large result set ({count} leads) stored in filesystem"
                }
            else:
                result = {
                    "leads": leads,
                    "count": count
                }
            
            logger.info(f"Queried leads: {count} results, filters={filters}")
            if not wait_for_result:
                result["status"] = "enqueued_for_persistence"
                result["persistence_task_id"] = enqueue.get("persistence_task_id")
            return result
        
        return query_leads_tool

    def _create_query_conversations_tool(self):
        """Tool for querying conversations by filters via Persistence Agent"""

        @tool
        def query_conversations_tool(
            filters: Optional[dict] = None,
            limit: int = 100,
            wait_for_result: Optional[bool] = None,
        ) -> dict:
            """Query conversations from database with filters.

            Intended use: fetch a lead's conversation(s) before reading messages.
            Example filters: {"lead_id": "<uuid>"}
            """
            filters = filters if isinstance(filters, dict) else {}
            enqueue = self._enqueue_persistence_query_table(
                table="conversations",
                filters=filters,
                limit=limit,
                order_by="created_at",
                descending=True,
            )

            if wait_for_result is None:
                wait_for_result = os.getenv("LEADS_WAIT_FOR_PERSISTENCE_RESULTS", "0").lower() in (
                    "1",
                    "true",
                    "yes",
                )

            if wait_for_result:
                payload = self._wait_for_agent_result(
                    result_stream=f"{self.tenant_id}:agents:persistence:results",
                    task_id=enqueue.get("persistence_task_id", ""),
                    timeout_s=int(os.getenv("LEADS_PERSISTENCE_WAIT_TIMEOUT_S", "30")),
                )
                if isinstance(payload, dict) and payload.get("status") == "success":
                    enqueue["persistence_result"] = payload.get("result")
                    enqueue["persistence_status"] = "success"
                else:
                    enqueue["persistence_status"] = "timeout"

            return enqueue

        return query_conversations_tool

    def _create_query_messages_tool(self):
        """Tool for querying messages by filters via Persistence Agent"""

        @tool
        def query_messages_tool(
            filters: Optional[dict] = None,
            limit: int = 200,
            wait_for_result: Optional[bool] = None,
        ) -> dict:
            """Query messages from database with filters.

            Example filters: {"conversation_id": "<uuid>"}
            """
            filters = filters if isinstance(filters, dict) else {}
            enqueue = self._enqueue_persistence_query_table(
                table="messages",
                filters=filters,
                limit=limit,
                order_by="created_at",
                descending=True,
            )

            if wait_for_result is None:
                wait_for_result = os.getenv("LEADS_WAIT_FOR_PERSISTENCE_RESULTS", "0").lower() in (
                    "1",
                    "true",
                    "yes",
                )

            if wait_for_result:
                payload = self._wait_for_agent_result(
                    result_stream=f"{self.tenant_id}:agents:persistence:results",
                    task_id=enqueue.get("persistence_task_id", ""),
                    timeout_s=int(os.getenv("LEADS_PERSISTENCE_WAIT_TIMEOUT_S", "30")),
                )
                if isinstance(payload, dict) and payload.get("status") == "success":
                    enqueue["persistence_result"] = payload.get("result")
                    enqueue["persistence_status"] = "success"
                else:
                    enqueue["persistence_status"] = "timeout"

            return enqueue

        return query_messages_tool
    
    def _create_move_lead_stage_tool(self):
        """Tool for moving lead to new pipeline stage"""
        
        @tool
        def move_lead_stage_tool(lead_id: str, to_stage: str) -> dict:
            """
            Move lead to a new pipeline stage.
            
            This is a DETERMINISTIC operation - no AI reasoning needed.
            Valid stages: new, contacted, qualified, demo_scheduled, closed_won, closed_lost
            
            Args:
                lead_id: Lead UUID
                to_stage: Target stage
            
            Returns:
                {"lead_id": str, "stage": str, "status": str}
            """
            valid_stages = ["new", "contacted", "qualified", "demo_scheduled", "closed_won", "closed_lost"]
            
            if to_stage not in valid_stages:
                return {
                    "status": "error",
                    "error": f"Invalid stage: {to_stage}",
                    "valid_stages": valid_stages
                }
            
            # TODO: Integrate with actual persistence layer
            # from agent.operational_agents.persistence_agent.facade import PersistenceFacade
            # facade = PersistenceFacade(self.tenant_id)
            # facade.update_lead(lead_id, {"stage": to_stage, "stage_changed_at": datetime.utcnow()})
            
            result = {
                "lead_id": lead_id,
                "stage": to_stage,
                "status": "moved",
                "moved_at": datetime.utcnow().isoformat()
            }
            
            logger.info(f"Moved lead {lead_id} to stage: {to_stage}")
            return result
        
        return move_lead_stage_tool
    
    # ==================== SUBAGENT DELEGATION TOOLS ====================
    
    def _create_delegate_to_rag_agent_tool(self):
        """Tool for delegating enrichment to RAG Agent"""
        
        @tool
        def delegate_to_rag_agent_tool(lead_id: str, enrichment_query: str) -> dict:
            """
            Delegate lead enrichment to RAG Agent (complex operation).
            
            RAG Agent will:
            1. Query vector database for relevant company/industry data
            2. Extract structured fields
            3. Update lead with enriched data
            
            Args:
                lead_id: Lead UUID to enrich
                enrichment_query: What to enrich (e.g., "company info", "industry data")
            
            Returns:
                {"task_id": str, "status": str, "delegated_to": "rag_agent"}
            """
            logger.info(f"[TOOL CALL] delegate_to_rag_agent_tool invoked with lead_id={lead_id}, query={enrichment_query}")
            
            task_id = f"rag_task_{uuid.uuid4()}"
            
            # Enqueue task to RAG Agent stream
            stream_name = f"{self.tenant_id}:agents:rag:tasks"
            assert_agents_stream(stream_name)
            logger.info(f"[TOOL CALL] Enqueuing to stream: {stream_name}")
            
            # Create payload
            payload = {
                "lead_id": lead_id,
                "query": enrichment_query,
                "operation": "enrich_lead",
                "delegated_by": "leads_orchestrator",
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Create typed envelope
            envelope = create_task_envelope(
                source="leads_orchestrator",
                task_id=task_id,
                payload=payload,
                destination="rag_agent",
                tenant_id=self.tenant_id
            )
            
            self.redis.xadd(
                stream_name,
                to_redis_fields(envelope)
            )
            
            logger.info(f"[TOOL CALL] Delegated enrichment to RAG Agent: {task_id}")
            
            return {
                "task_id": task_id,
                "status": "enqueued",
                "delegated_to": "rag_agent",
                "lead_id": lead_id,
                "message": "RAG Agent will enrich lead asynchronously"
            }
        
        return delegate_to_rag_agent_tool
    
    def _create_delegate_to_persistence_agent_tool(self):
        """Tool for delegating bulk operations to Persistence Agent"""
        
        @tool
        def delegate_to_persistence_agent_tool(operation: str, data: dict) -> dict:
            """
            Delegate bulk operations to Persistence Agent (complex operation).
            
            Persistence Agent handles:
            - Bulk imports (> 100 leads)
            - Batch updates
            - Transaction management
            - Error handling for large datasets
            
            Args:
                operation: Operation type ("bulk_import", "batch_update")
                data: Operation data ({"leads": [...]} or {"updates": [...]})
            
            Returns:
                {"task_id": str, "status": str, "delegated_to": "persistence_agent"}
            """
            task_id = f"persist_task_{uuid.uuid4()}"
            
            # Create payload
            payload = {
                "operation": operation,
                "data": data,
                "delegated_by": "leads_orchestrator",
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Enqueue task to Persistence Agent stream (correct naming)
            stream_name = f"{self.tenant_id}:agents:persistence:tasks"
            assert_agents_stream(stream_name)
            
            # Create typed envelope
            envelope = create_task_envelope(
                source="leads_orchestrator",
                task_id=task_id,
                payload=payload,
                destination="persistence_agent",
                tenant_id=self.tenant_id
            )
            
            self.redis.xadd(
                stream_name,
                to_redis_fields(envelope)
            )
            
            logger.info(f"Delegated {operation} to Persistence Agent: {task_id} stream={stream_name}")
            
            return {
                "task_id": task_id,
                "status": "enqueued",
                "delegated_to": "persistence_agent",
                "operation": operation,
                "message": "Persistence Agent will process batch operation asynchronously"
            }
        
        return delegate_to_persistence_agent_tool

    def _create_compound_persistence_tool(self):
        """Tool for delegating rich compound persistence flows to Persistence Agent"""

        @tool
        def compound_persistence_tool(
            steps: List[dict],
            continue_on_skip: bool = False,
            rollback_on_failure: bool = True,
            wait_for_result: Optional[bool] = None,
            metadata: Optional[dict] = None,
        ) -> dict:
            """
            Execute multi-step database operations (create/update/upsert/delete) with FK refs and rollback.

            - Use $ref:step.field to reference prior step outputs (supports nested paths)
            - Supported step operations: create, update, upsert, delete
            - Per-step on_error: fail (default), skip, warn
            - Global flags: rollback_on_failure, continue_on_skip

            Args:
                steps: List of step dicts matching CompoundPayload schema
                continue_on_skip: If False, abort on first skipped step
                rollback_on_failure: Issue rollbacks for completed steps when a failure occurs
                wait_for_result: If True, block for PersistenceAgent result stream
                metadata: Optional metadata forwarded to PersistenceAgent
            """

            normalized_steps = steps if isinstance(steps, list) else []
            payload = {
                "steps": normalized_steps,
                "continue_on_skip": bool(continue_on_skip),
                "rollback_on_failure": bool(rollback_on_failure),
            }
            if isinstance(metadata, dict):
                payload["metadata"] = metadata

            enqueue = self._enqueue_persistence_compound(payload)

            if wait_for_result is None:
                wait_for_result = os.getenv("LEADS_WAIT_FOR_PERSISTENCE_RESULTS", "0").lower() in ("1", "true", "yes")

            if wait_for_result:
                payload = self._wait_for_agent_result(
                    result_stream=f"{self.tenant_id}:agents:persistence:results",
                    task_id=enqueue.get("persistence_task_id", ""),
                    timeout_s=int(os.getenv("LEADS_PERSISTENCE_WAIT_TIMEOUT_S", "30")),
                )
                if isinstance(payload, dict) and payload.get("status") == "success":
                    enqueue["persistence_result"] = payload.get("result")
                    enqueue["persistence_status"] = "success"
                else:
                    enqueue["persistence_status"] = "timeout"

            return enqueue

        return compound_persistence_tool

    def _create_store_inbound_email_tool(self):
        """Tool for storing inbound email event (lead, conversation, message) via compound flow"""

        @tool
        def store_inbound_email_tool(
            email_event: dict,
            lead_data: Optional[dict] = None,
            cleanup_staging: bool = False,
            lead_resolution: Optional[dict] = None,
            wait_for_result: Optional[bool] = None,
        ) -> dict:
            """
            Persist inbound email into leads/conversations/messages tables with FK-safe steps.

            - Steps: route to leads vs staging based on optional lead_resolution; upsert conversation; create inbound message
            - Uses $ref chaining between steps; safe for missing thread_id
            - Optional cleanup of staging_leads by sender email when a lead match is found
            """

            lead_data = lead_data or {}
            steps, promotion_candidate = self._build_inbound_email_steps(
                email_event=email_event,
                lead_data=lead_data,
                cleanup_staging=cleanup_staging,
                lead_resolution=lead_resolution,
            )
            enqueue = self._enqueue_persistence_compound(
                {
                    "steps": steps,
                    "rollback_on_failure": True,
                    "continue_on_skip": True,
                }
            )

            if promotion_candidate:
                enqueue["promotion"] = self._enqueue_persistence_promote_staging_lead(
                    staging_lead_id=promotion_candidate.get("staging_lead_id"),
                    lead_score=promotion_candidate.get("lead_score", 50),
                    campaign_id=promotion_candidate.get("campaign_id"),
                    qualification_status=promotion_candidate.get("qualification_status", "qualified"),
                )

            if wait_for_result is None:
                wait_for_result = os.getenv("LEADS_WAIT_FOR_PERSISTENCE_RESULTS", "0").lower() in ("1", "true", "yes")

            if wait_for_result:
                payload = self._wait_for_agent_result(
                    result_stream=f"{self.tenant_id}:agents:persistence:results",
                    task_id=enqueue.get("persistence_task_id", ""),
                    timeout_s=int(os.getenv("LEADS_PERSISTENCE_WAIT_TIMEOUT_S", "30")),
                )
                if isinstance(payload, dict) and payload.get("status") == "success":
                    enqueue["persistence_result"] = payload.get("result")
                    enqueue["persistence_status"] = "success"
                else:
                    enqueue["persistence_status"] = "timeout"

            return enqueue

        return store_inbound_email_tool

    def _create_delegate_to_rag_context_tool(self):
        """Tool for delegating lead context retrieval (identity + history) to RAG Agent"""

        @tool
        def delegate_to_rag_context_tool(
            email: Optional[str] = None,
            lead_id: Optional[str] = None,
            conversation_limit: int = 5,
            message_limit: int = 50,
        ) -> dict:
            """Fetch lead record plus recent conversations/messages via RAG (read-only)."""
            task_id = f"rag_ctx_{uuid.uuid4()}"
            payload = {
                "operation": "get_lead_context",
                "email": email,
                "lead_id": lead_id,
                "conversation_limit": conversation_limit,
                "message_limit": message_limit,
                "delegated_by": "leads_orchestrator",
                "timestamp": datetime.utcnow().isoformat(),
            }

            stream_name = f"{self.tenant_id}:agents:rag:tasks"
            assert_agents_stream(stream_name)

            envelope = create_task_envelope(
                source="leads_orchestrator",
                task_id=task_id,
                payload=payload,
                destination="rag_agent",
                tenant_id=self.tenant_id,
            )

            self.redis.xadd(stream_name, to_redis_fields(envelope))

            return {
                "task_id": task_id,
                "status": "enqueued",
                "delegated_to": "rag_agent",
                "operation": "get_lead_context",
                "message": "RAG Agent will retrieve lead context asynchronously",
            }

        return delegate_to_rag_context_tool
    
    def _create_delegate_to_deduplication_agent_tool(self):
        """Tool for delegating duplicate detection"""
        
        @tool
        def delegate_to_deduplication_agent_tool(
            lead_ids: Optional[List[str]] = None,
            similarity_threshold: float = 0.85
        ) -> dict:
            """
            Delegate duplicate detection to Deduplication Agent (complex operation).
            
            Deduplication Agent will:
            1. Find potential duplicates using fuzzy matching
            2. Calculate similarity scores
            3. Determine canonical lead (most complete)
            4. Propose merge strategy
            
            Args:
                lead_ids: Specific leads to check (optional, checks all if None)
                similarity_threshold: Minimum similarity score (0.0-1.0)
            
            Returns:
                {"task_id": str, "status": str, "delegated_to": "deduplication_agent"}
            """
            # NOTE: DeduplicationAgent is not implemented in Tier 3 at the moment.
            # We intentionally do NOT enqueue to a Redis stream to avoid dangling work.
            return {
                "status": "not_implemented",
                "delegated_to": "deduplication_agent",
                "lead_ids": lead_ids or "all",
                "similarity_threshold": similarity_threshold,
                "message": "Deduplication Agent is not implemented yet; skipping delegation",
            }
        
        return delegate_to_deduplication_agent_tool
    
    # ==================== EXECUTION METHODS ====================
    
    def execute(self, task_data_or_goal, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute a lead operation goal.
        
        Args:
            task_data_or_goal: User's goal/request (string) or task data dict
            context: Optional context (lead_data, filters, etc.)
        
        Returns:
            Execution result with status and output
        """
        start_time = datetime.now()
        execution_id = f"exec_{start_time.timestamp()}"

        delegations: Optional[Dict[str, Any]] = None
        context_depth: Optional[str] = None
        email_event: Optional[Dict[str, Any]] = None
        
        # Extract goal from task_data if dict passed
        if isinstance(task_data_or_goal, dict):
            goal = task_data_or_goal.get("goal")
            # Handle nested payload from Manager
            if not goal and "payload" in task_data_or_goal:
                inner = task_data_or_goal["payload"]
                if isinstance(inner, dict):
                    goal = inner.get("goal")
                    # Merge contexts if needed
                    if not context:
                        # Some producers send `context`, older paths used `data`
                        inner_context = inner.get("context")
                        if isinstance(inner_context, dict):
                            context = inner_context
                        else:
                            context = inner.get("data", {})
            
            goal = goal or ""
            if not context:
                # Some producers send `context`, older paths used `data`
                outer_context = task_data_or_goal.get("context")
                if isinstance(outer_context, dict):
                    context = outer_context
                else:
                    context = task_data_or_goal.get("data", {})

            # Extract inner_payload BEFORE referencing it
            inner_payload = task_data_or_goal.get("payload") if isinstance(task_data_or_goal.get("payload"), dict) else None

            if context_depth is None:
                context_depth = task_data_or_goal.get("context_depth") or (
                    inner_payload.get("context_depth") if isinstance(inner_payload, dict) else None
                )
            if email_event is None:
                email_event = self._extract_email_event(context) or (
                    inner_payload.get("email_event") if isinstance(inner_payload, dict) else None
                )

            # Deterministic delegation hint (Manager->Leads passes original request under task_data_or_goal['payload'])
            if isinstance(task_data_or_goal.get("delegations"), dict):
                delegations = task_data_or_goal.get("delegations")
            if delegations is None and isinstance(inner_payload, dict) and isinstance(inner_payload.get("delegations"), dict):
                delegations = inner_payload.get("delegations")
        else:
            goal = task_data_or_goal
        
        logger.info(f"LeadsOrchestrator executing: {task_data_or_goal} (id={execution_id})")
        logger.info(f"Extracted goal: {goal}")
        logger.info(f"Context: {context}")

        correlation_id = None
        if isinstance(task_data_or_goal, dict):
            correlation_id = task_data_or_goal.get("correlation_id") or task_data_or_goal.get("task_id")
            if isinstance(task_data_or_goal.get("payload"), dict):
                inner = task_data_or_goal.get("payload")
                correlation_id = (
                    correlation_id
                    or inner.get("correlation_id")
                    or inner.get("task_id")
                    or inner.get("id")
                )
        correlation_id = correlation_id or execution_id

        _trace_log(
            "leads",
            correlation_id=correlation_id,
            task_id=execution_id,
            step="received",
            detail="leads_orchestrator_execute",
            goal=goal,
        )

        # Fast-path deep reply handling: fetch context via RAG, assemble ReplyPacket for outbound.
        if (context_depth or "").lower() == "deep" and isinstance(email_event, dict):
            try:
                return self._handle_deep_reply_flow(
                    goal=goal,
                    context=context or {},
                    email_event=email_event,
                    execution_id=execution_id,
                    start_time=start_time,
                )
            except Exception as e:
                logger.warning(f"Deep reply flow failed, falling back to normal agent invoke: {e}")

        # Fast-path qualify_lead intent: evaluate staging lead for promotion
        intent = None
        if isinstance(task_data_or_goal, dict):
            intent = task_data_or_goal.get("intent") or (
                task_data_or_goal.get("payload", {}).get("intent") if isinstance(task_data_or_goal.get("payload"), dict) else None
            )
        if intent == "qualify_lead" or (goal and "qualify" in goal.lower() and "staging" in goal.lower()):
            staging_lead_id = None
            campaign_id = None
            if isinstance(context, dict):
                staging_lead_id = context.get("staging_lead_id") or context.get("lead_id")
                campaign_id = context.get("campaign_id")
            if isinstance(task_data_or_goal, dict):
                staging_lead_id = staging_lead_id or task_data_or_goal.get("staging_lead_id")
                campaign_id = campaign_id or task_data_or_goal.get("campaign_id")
            
            if staging_lead_id:
                return self._handle_qualify_lead(
                    staging_lead_id=staging_lead_id,
                    execution_id=execution_id,
                    start_time=start_time,
                    campaign_id=campaign_id,
                )

        # Deterministic inbound email persistence: do NOT treat inbound email events as
        # conversation-context retrieval requests just because the payload contains
        # words like "thread"/"conversation".
        if intent == "inbound" and isinstance(email_event, dict):
            try:
                lead_data = {}
                cleanup_staging = bool(os.getenv("LEADS_CLEANUP_STAGING_ON_INBOUND", "0").lower() in ("1", "true", "yes"))
                lead_resolution_payload = None
                email_classification = None
                conversation_history = None

                if isinstance(context, dict):
                    if isinstance(context.get("lead_data"), dict):
                        lead_data = context.get("lead_data") or {}
                    cleanup_staging = bool(context.get("cleanup_staging", cleanup_staging))
                    if isinstance(context.get("lead_resolution"), dict):
                        lead_resolution_payload = context.get("lead_resolution")
                    elif isinstance(context.get("lead_resolution_payload"), dict):
                        lead_resolution_payload = context.get("lead_resolution_payload")
                    if isinstance(context.get("classification"), dict):
                        email_classification = context.get("classification")
                    if isinstance(context.get("conversation_history"), list):
                        conversation_history = context.get("conversation_history")

                steps, promotion_candidate = self._build_inbound_email_steps(
                    email_event=email_event,
                    lead_data=lead_data,
                    cleanup_staging=cleanup_staging,
                    lead_resolution=lead_resolution_payload,
                    email_classification=email_classification,
                    conversation_history=conversation_history,
                )
                store_status = self._enqueue_persistence_compound(
                    {
                        "steps": steps,
                        "rollback_on_failure": True,
                        "continue_on_skip": True,
                        "metadata": {"source": "leads_orchestrator", "path": "inbound_deterministic"},
                    }
                )

                promotion_status = None
                if promotion_candidate:
                    promotion_status = self._enqueue_persistence_promote_staging_lead(
                        staging_lead_id=promotion_candidate.get("staging_lead_id"),
                        lead_score=promotion_candidate.get("lead_score", 50),
                        campaign_id=promotion_candidate.get("campaign_id"),
                        qualification_status=promotion_candidate.get("qualification_status", "qualified"),
                    )

                elapsed = (datetime.now() - start_time).total_seconds() * 1000
                return {
                    "success": True,
                    "execution_id": execution_id,
                    "orchestrator": "leads",
                    "path": "inbound_persist",
                    "store_inbound": store_status,
                    "promotion": promotion_status,
                    "latency_ms": elapsed,
                    "timestamp": start_time.isoformat(),
                }
            except Exception as e:
                logger.error(f"Inbound deterministic persistence failed: {e}", exc_info=True)
                elapsed = (datetime.now() - start_time).total_seconds() * 1000
                return {
                    "success": False,
                    "execution_id": execution_id,
                    "orchestrator": "leads",
                    "path": "inbound_persist",
                    "error": str(e),
                    "latency_ms": elapsed,
                    "timestamp": start_time.isoformat(),
                }

        # Deterministic conversation-context retrieval (do not defer to the LLM).
        if self._is_conversation_context_goal(goal, context):
            return self._handle_conversation_context_request(
                goal=goal,
                context=context or {},
                email_event=email_event,
                execution_id=execution_id,
                start_time=start_time,
                correlation_id=correlation_id,
            )

        # Deterministic-first path: execute explicit delegations without LLM/tool-choice dependency
        if isinstance(delegations, dict) and delegations:
            results: Dict[str, Any] = {}
            try:
                for key, value in delegations.items():
                    normalized = str(key).strip().lower()

                    if normalized in {"write_lead", "write_lead_tool"}:
                        lead_data = None
                        if isinstance(value, dict) and isinstance(value.get("lead_data"), dict):
                            lead_data = value.get("lead_data")
                        elif isinstance(value, dict):
                            lead_data = value
                        else:
                            lead_data = {}
                        results["write_lead"] = self._enqueue_persistence_write_lead(lead_data)
                        continue

                    if normalized in {"read_lead", "read_lead_tool"}:
                        lead_id = None
                        if isinstance(value, dict):
                            lead_id = value.get("lead_id") or value.get("id")
                        elif isinstance(value, str):
                            lead_id = value
                        if not lead_id:
                            results["read_lead"] = {"status": "error", "error": "Missing lead_id"}
                        else:
                            results["read_lead"] = self._enqueue_persistence_read_lead(str(lead_id))
                        continue

                    results[key] = {"status": "ignored", "reason": "Unknown delegation"}

                elapsed = (datetime.now() - start_time).total_seconds() * 1000
                return {
                    "success": True,
                    "execution_id": execution_id,
                    "orchestrator": "leads",
                    "path": "deterministic_delegations",
                    "delegations": results,
                    "latency_ms": elapsed,
                    "timestamp": start_time.isoformat(),
                }
            except Exception as e:
                logger.error(f"Deterministic delegations failed: {e}")
                elapsed = (datetime.now() - start_time).total_seconds() * 1000
                return {
                    "success": False,
                    "execution_id": execution_id,
                    "orchestrator": "leads",
                    "path": "deterministic_delegations",
                    "error": str(e),
                    "latency_ms": elapsed,
                    "timestamp": start_time.isoformat(),
                }
        
        try:
            # Prepare messages for Deep Agent
            messages = [("user", goal)]
            if context:
                context_str = json.dumps(context)
                messages.insert(0, ("system", f"Additional context: {context_str}"))
            
            logger.info(f"Invoking Deep Agent with messages: {messages}")
            
            # Execute Deep Agent (with TodoList, Filesystem, SubAgent middleware)
            result = self.agent.invoke({"messages": messages})
            
            logger.info(f"Deep Agent result: {result}")
            
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            logger.info(f"LeadsOrchestrator completed in {elapsed:.2f}ms")
            
            # Extract result from Deep Agent response
            result_message = result.get("messages", [])[-1] if result.get("messages") else None
            result_content = result_message.content if hasattr(result_message, "content") else str(result_message)
            
            return {
                "success": True,
                "execution_id": execution_id,
                "orchestrator": "leads",
                "result": result_content,
                "latency_ms": elapsed,
                "timestamp": start_time.isoformat(),
                "middleware_used": {
                    "todo_list": True,
                    "filesystem": True,
                    "subagents": True
                }
            }
            
        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"LeadsOrchestrator execution failed: {e}")
            
            return {
                "success": False,
                "execution_id": execution_id,
                "orchestrator": "leads",
                "error": str(e),
                "latency_ms": elapsed,
                "timestamp": start_time.isoformat()
            }

    def _handle_qualify_lead(
        self,
        *,
        staging_lead_id: str,
        execution_id: str,
        start_time: datetime,
        campaign_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Handle qualify_lead intent: evaluate staging lead and promote if qualified.
        
        Args:
            staging_lead_id: UUID of the staging lead to evaluate
            execution_id: Execution tracking ID
            start_time: Start time for latency calculation
            campaign_id: Optional campaign to link on promotion
            
        Returns:
            Result dict with qualification decision and promotion status
        """
        try:
            # 1. Fetch staging lead and conversation history via RAG
            rag_task = self._enqueue_rag_context_task(
                email=None,
                lead_id=staging_lead_id,
                context_depth="deep",
            )
            
            rag_timeout = int(os.getenv("LEADS_RAG_CONTEXT_TIMEOUT_S", "30"))
            rag_payload = self._wait_for_agent_result(
                result_stream=f"{self.tenant_id}:agents:rag:results",
                task_id=rag_task.get("task_id", ""),
                timeout_s=rag_timeout,
            )
            
            if not rag_payload or rag_payload.get("status") != "success":
                elapsed = (datetime.now() - start_time).total_seconds() * 1000
                return {
                    "success": False,
                    "execution_id": execution_id,
                    "orchestrator": "leads",
                    "path": "qualify_lead",
                    "error": "Failed to retrieve staging lead context",
                    "rag_status": rag_payload.get("status") if rag_payload else "timeout",
                    "latency_ms": elapsed,
                }
            
            # 2. Extract lead data and conversation history
            lead_record = rag_payload.get("lead") or {}
            conversations = rag_payload.get("conversations") or []
            messages = rag_payload.get("messages") or []
            
            # Build conversation history for scoring
            conversation_history = [
                {
                    "content": msg.get("text_content") or msg.get("content") or "",
                    "direction": msg.get("direction") or "unknown",
                    "sender": msg.get("sender") or msg.get("sender_type") or "",
                }
                for msg in messages
            ]
            
            # 3. Run qualification scoring
            if not QUALIFICATION_ENABLED or score_lead_sync is None:
                elapsed = (datetime.now() - start_time).total_seconds() * 1000
                return {
                    "success": False,
                    "execution_id": execution_id,
                    "orchestrator": "leads",
                    "path": "qualify_lead",
                    "error": "Qualification scoring not available",
                    "latency_ms": elapsed,
                }
            
            qualification_result = score_lead_sync(
                lead_data=lead_record,
                conversation_history=conversation_history,
                email_classification={},  # No email classification for manual qualify
                lead_source="staging_leads",
                email_direction="inbound",
            )
            
            logger.info(
                "[QUALIFY_LEAD] staging_lead_id=%s score=%d decision=%s promote=%s",
                staging_lead_id,
                qualification_result.score,
                qualification_result.decision,
                qualification_result.promote,
            )
            
            # 4. If qualified, trigger promotion via persistence agent
            promotion_result = None
            if qualification_result.promote:
                task_id = f"persist_promote_{uuid.uuid4()}"
                payload = build_promotion_task_payload(
                    staging_lead_id=staging_lead_id,
                    decision=getattr(qualification_result, "decision", None),
                    score=qualification_result.score,
                    campaign_id=campaign_id,
                    delegated_by="leads_orchestrator",
                    timestamp=datetime.utcnow().isoformat(),
                )
                
                stream_name = f"{self.tenant_id}:agents:persistence:tasks"
                assert_agents_stream(stream_name)
                
                envelope = create_task_envelope(
                    source="leads_orchestrator",
                    task_id=task_id,
                    payload=payload,
                    destination="persistence_agent",
                    tenant_id=self.tenant_id,
                )
                
                self.redis.xadd(stream_name, to_redis_fields(envelope))
                logger.info(f"[QUALIFY_LEAD] Enqueued promotion task_id={task_id}")
                
                # Wait for promotion result
                promotion_result = self._wait_for_agent_result(
                    result_stream=f"{self.tenant_id}:agents:persistence:results",
                    task_id=task_id,
                    timeout_s=30,
                )
            
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            return {
                "success": True,
                "execution_id": execution_id,
                "orchestrator": "leads",
                "path": "qualify_lead",
                "staging_lead_id": staging_lead_id,
                "qualification": {
                    "score": qualification_result.score,
                    "decision": qualification_result.decision,
                    "promote": qualification_result.promote,
                    "fast_track": qualification_result.fast_track,
                    "signals": qualification_result.signals,
                    "reasoning": qualification_result.reasoning,
                },
                "promoted": qualification_result.promote,
                "promotion_result": promotion_result,
                "latency_ms": elapsed,
                "timestamp": start_time.isoformat(),
            }
            
        except Exception as e:
            logger.error(f"[QUALIFY_LEAD] Failed: {e}")
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            return {
                "success": False,
                "execution_id": execution_id,
                "orchestrator": "leads",
                "path": "qualify_lead",
                "error": str(e),
                "latency_ms": elapsed,
            }

    def _handle_deep_reply_flow(
        self,
        *,
        goal: str,
        context: Dict[str, Any],
        email_event: Dict[str, Any],
        execution_id: str,
        start_time: datetime,
    ) -> Dict[str, Any]:
        email = email_event.get("from") or email_event.get("email") or email_event.get("sender")
        lead_id = context.get("lead_id") if isinstance(context, dict) else None

        store_status: Dict[str, Any] = {"status": "skipped"}
        stored_ok = False
        write_markers: List[str] = []

        rag_task = self._enqueue_rag_context_task(
            email=email,
            lead_id=lead_id,
            subject=email_event.get("subject") if isinstance(email_event, dict) else None,
            thread_id=(email_event.get("thread_id") if isinstance(email_event, dict) else None),
            context_depth=(context.get("context_depth") if isinstance(context, dict) else "deep"),
        )
        wait_for_rag = os.getenv("LEADS_WAIT_FOR_RAG_CONTEXT", "1").lower() in ("1", "true", "yes")
        rag_timeout = int(os.getenv("LEADS_RAG_CONTEXT_TIMEOUT_S", "20"))
        rag_payload = None
        if wait_for_rag:
            logger.info(
                "[RAG_WAIT] Waiting for RAG result: task_id=%s timeout=%ss email=%s",
                rag_task.get("task_id", ""),
                rag_timeout,
                email,
            )
            rag_payload = self._wait_for_agent_result(
                result_stream=f"{self.tenant_id}:agents:rag:results",
                task_id=rag_task.get("task_id", ""),
                timeout_s=rag_timeout,
            )
            if rag_payload is None:
                logger.error(
                    "[RAG_TIMEOUT] RAG Agent did not respond within %ss! "
                    "task_id=%s email=%s. Check if RAG consumer is running. "
                    "Run: python -m tiers.tier_3.rag_agent.consumer",
                    rag_timeout,
                    rag_task.get("task_id", ""),
                    email,
                )
            else:
                logger.info(
                    "[RAG_SUCCESS] RAG returned: status=%s lead_source=%s lead_id=%s conversations=%d messages=%d",
                    rag_payload.get("status"),
                    rag_payload.get("lead_source"),
                    (rag_payload.get("lead") or {}).get("id") if isinstance(rag_payload.get("lead"), dict) else None,
                    len(rag_payload.get("conversations") or []),
                    len(rag_payload.get("messages") or []),
                )

        lead_resolution_payload: Dict[str, Any] = {}
        if isinstance(rag_payload, dict):
            lead_record = rag_payload.get("lead") if isinstance(rag_payload, dict) else None
            lead_resolution_payload = {
                "lead_id": (lead_record or {}).get("id") if isinstance(lead_record, dict) else None,
                "lead_source": rag_payload.get("lead_source"),
                "status": rag_payload.get("status"),
                "match_reason": rag_payload.get("match_reason"),
            }

        logger.info(
            "[INBOUND_PERSIST] lead_resolution=%s email=%s lead_id=%s",
            lead_resolution_payload,
            email,
            lead_id,
        )

        # Store inbound email with routing hints from RAG (if available) so we attach to the right table.
        store_enabled = os.getenv("LEADS_STORE_INBOUND_EMAIL", "1").lower() in ("1", "true", "yes")
        if store_enabled and isinstance(email_event, dict):
            try:
                lead_data = {}
                if isinstance(context, dict) and isinstance(context.get("lead_data"), dict):
                    lead_data = context.get("lead_data") or {}

                steps, promotion_candidate = self._build_inbound_email_steps(
                    email_event=email_event,
                    lead_data=lead_data,
                    cleanup_staging=bool(os.getenv("LEADS_CLEANUP_STAGING_ON_INBOUND", "0").lower() in ("1", "true", "yes")),
                    lead_resolution=lead_resolution_payload,
                )
                store_status = self._enqueue_persistence_compound(
                    {
                        "steps": steps,
                        "rollback_on_failure": True,
                        "continue_on_skip": True,
                        "metadata": {"source": "leads_orchestrator", "path": "deep_reply_flow"},
                    }
                )
                promotion_status = None
                if promotion_candidate:
                    promotion_status = self._enqueue_persistence_promote_staging_lead(
                        staging_lead_id=promotion_candidate.get("staging_lead_id"),
                        lead_score=promotion_candidate.get("lead_score", 50),
                        campaign_id=promotion_candidate.get("campaign_id"),
                        qualification_status=promotion_candidate.get("qualification_status", "qualified"),
                    )
                logger.info(
                    "[INBOUND_PERSIST] enqueued compound steps=%s task_id=%s lead_resolution=%s",
                    len(steps),
                    store_status.get("persistence_task_id") if isinstance(store_status, dict) else None,
                    lead_resolution_payload,
                )
                stored_ok = True
                if isinstance(store_status, dict) and store_status.get("persistence_task_id"):
                    write_markers.append(f"persistence_task_id:{store_status.get('persistence_task_id')}")
                if promotion_status and isinstance(promotion_status, dict) and promotion_status.get("persistence_task_id"):
                    write_markers.append(f"persistence_task_id:{promotion_status.get('persistence_task_id')}")
            except Exception as e:
                logger.warning(f"Failed to store inbound email event; continuing deep reply flow: {e}")
        else:
            logger.info(
                "[INBOUND_PERSIST] skipped enqueue store_enabled=%s email_event=%s",
                store_enabled,
                bool(email_event),
            )

        reply_packet_dict = self._build_reply_packet_from_rag(
            rag_payload=rag_payload,
            email_event=email_event,
            goal=goal,
            stored_ok=stored_ok,
            write_markers=write_markers,
            lead_resolution_payload=lead_resolution_payload,
        )

        elapsed = (datetime.now() - start_time).total_seconds() * 1000
        return {
            "success": True,
            "execution_id": execution_id,
            "orchestrator": "leads",
            "path": "deep_reply_packet",
            "store_inbound": store_status,
            "rag_task": rag_task,
            "reply_packet": reply_packet_dict,
            "latency_ms": elapsed,
            "timestamp": start_time.isoformat(),
        }

    def _enqueue_rag_context_task(
        self,
        *,
        email: Optional[str],
        lead_id: Optional[str],
        subject: Optional[str] = None,
        thread_id: Optional[str] = None,
        context_depth: str = "deep",
    ) -> Dict[str, Any]:
        task_id = f"rag_ctx_{uuid.uuid4()}"
        # For inbound reply flows we need lead profile + selected thread + message history.
        # Use build_reply_context (thread_id > subject > recency) instead of get_lead_context.
        # This is intentionally small and stable for low-token debugging.
        query_plan = {
            "tables": [
                "leads",
                "staging_leads",
                "conversations",
                "staging_conversations",
                "messages",
                "staging_messages",
            ],
            "match_keys": ["lead_id", "email", "thread_id", "subject"],
            "operation": "build_reply_context",
            "context_depth": context_depth,
        }

        max_messages = 200 if str(context_depth).lower() == "deep" else 50

        # RAGAgent.execute expects a goal/record-style payload for deterministic lookup.
        payload = {
            "goal": "build_reply_context",
            "entity_type": "lead",
            "record": {"email": email, "lead_id": lead_id},
            "operation": "build_reply_context",
            "email": email,
            "lead_id": lead_id,
            "thread_id": thread_id,
            "subject": subject,
            "max_messages": max_messages,
            "include_lead_profile": True,
            "include_all_threads": True,
            "query_plan": query_plan,
            "task_id": task_id,
            "delegated_by": "leads_orchestrator",
            "timestamp": datetime.utcnow().isoformat(),
        }
        stream_name = f"{self.tenant_id}:agents:rag:tasks"
        assert_agents_stream(stream_name)
        envelope = create_task_envelope(
            source="leads_orchestrator",
            task_id=task_id,
            payload=payload,
            destination="rag_agent",
            tenant_id=self.tenant_id,
        )
        self.redis.xadd(stream_name, to_redis_fields(envelope))
        return {
            "status": "enqueued",
            "delegated_to": "rag_agent",
            "task_id": task_id,
            "stream": stream_name,
            "query_plan": query_plan,
        }

    def _extract_email_event(self, ctx: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not isinstance(ctx, dict):
            return None
        if isinstance(ctx.get("email_event"), dict):
            return ctx.get("email_event")
        return None

    def _is_conversation_context_goal(self, goal: str, context: Optional[Dict[str, Any]]) -> bool:
        text_parts: List[str] = [goal or ""]
        if isinstance(context, dict) and context:
            try:
                text_parts.append(json.dumps(context, default=str))
            except Exception:
                pass
        text = " ".join(text_parts).lower()
        keywords = [
            "conversation",
            "thread",
            "history",
            "previous message",
            "previous messages",
            "last message",
            "last conversation",
        ]
        return any(k in text for k in keywords)

    def _handle_conversation_context_request(
        self,
        *,
        goal: str,
        context: Dict[str, Any],
        email_event: Optional[Dict[str, Any]],
        execution_id: str,
        start_time: datetime,
        correlation_id: str,
    ) -> Dict[str, Any]:
        lead_id = None
        email = None

        if isinstance(context, dict):
            lead_id = context.get("lead_id") or context.get("id")
            email = context.get("email") or context.get("lead_email")
            if isinstance(context.get("lead_data"), dict):
                lead_id = lead_id or context["lead_data"].get("id")
                email = email or context["lead_data"].get("email")

        if isinstance(email_event, dict):
            email = email or email_event.get("from") or email_event.get("email") or email_event.get("sender")

        if not lead_id and not email:
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            _trace_log(
                "leads",
                correlation_id=correlation_id,
                task_id=execution_id,
                step="failed",
                detail="conversation_context_missing_identifier",
                latency_ms=elapsed,
            )
            return {
                "success": False,
                "path": "conversation_context",
                "error": "missing_lead_identifier",
                "message": "Provide lead_id or email to retrieve conversation history",
                "execution_id": execution_id,
                "latency_ms": elapsed,
                "timestamp": start_time.isoformat(),
            }

        rag_task = self._enqueue_rag_context_task(email=email, lead_id=lead_id)

        _trace_log(
            "leads",
            correlation_id=correlation_id,
            task_id=execution_id,
            step="delegated",
            detail="delegate_to_rag_get_lead_context",
            delegated_task_id=rag_task.get("task_id"),
            stream=rag_task.get("stream"),
        )

        rag_payload = None
        wait_for_rag = os.getenv("LEADS_WAIT_FOR_RAG_CONTEXT", "1").lower() in ("1", "true", "yes")
        if wait_for_rag:
            rag_payload = self._wait_for_agent_result(
                result_stream=f"{self.tenant_id}:agents:rag:results",
                task_id=rag_task.get("task_id", ""),
                timeout_s=int(os.getenv("LEADS_RAG_CONTEXT_TIMEOUT_S", "20")),
            )

        _trace_log(
            "leads",
            correlation_id=correlation_id,
            task_id=execution_id,
            step="waiting_result",
            detail="waiting_for_rag_context",
            delegated_task_id=rag_task.get("task_id"),
        )

        has_context = isinstance(rag_payload, dict) and bool(
            rag_payload.get("lead") or rag_payload.get("conversations") or rag_payload.get("messages")
        )

        if not rag_payload or not has_context:
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            _trace_log(
                "leads",
                correlation_id=correlation_id,
                task_id=execution_id,
                step="failed",
                detail="rag_context_unavailable",
                delegated_task_id=rag_task.get("task_id"),
                latency_ms=elapsed,
            )
            return {
                "success": False,
                "path": "conversation_context",
                "error": "rag_context_unavailable",
                "message": "Could not retrieve conversation history; RAG returned no context",
                "rag_task": rag_task,
                "rag_payload": rag_payload,
                "execution_id": execution_id,
                "latency_ms": elapsed,
                "timestamp": start_time.isoformat(),
            }

        elapsed = (datetime.now() - start_time).total_seconds() * 1000
        _trace_log(
            "leads",
            correlation_id=correlation_id,
            task_id=execution_id,
            step="completed",
            detail="conversation_context_ready",
            delegated_task_id=rag_task.get("task_id"),
            latency_ms=elapsed,
        )
        return {
            "success": True,
            "path": "conversation_context",
            "execution_id": execution_id,
            "rag_task": rag_task,
            "context": {
                "lead": rag_payload.get("lead"),
                "conversations": rag_payload.get("conversations"),
                "messages": rag_payload.get("messages"),
            },
            "latency_ms": elapsed,
            "timestamp": start_time.isoformat(),
        }

    def _build_reply_packet_from_rag(
        self,
        *,
        rag_payload: Optional[Dict[str, Any]],
        email_event: Dict[str, Any],
        goal: str,
        stored_ok: bool = False,
        write_markers: Optional[List[str]] = None,
        lead_resolution_payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        lead_record = None
        conversations: List[Dict[str, Any]] = []
        messages: List[Dict[str, Any]] = []
        status = "unknown"
        lead_source: Optional[str] = None
        query_trace: Optional[Dict[str, Any]] = None
        match_reason: Optional[Any] = None

        if isinstance(rag_payload, dict):
            lead_record = rag_payload.get("lead")
            # Handle both plural "conversations" (list) and singular "conversation" (dict)
            if isinstance(rag_payload.get("conversations"), list):
                conversations = rag_payload.get("conversations") or []
            elif isinstance(rag_payload.get("conversation"), dict):
                conversations = [rag_payload.get("conversation")]
            else:
                conversations = []
            messages = rag_payload.get("messages") or []
            status = rag_payload.get("status", "unknown")
            lead_source = rag_payload.get("lead_source")
            query_trace = rag_payload.get("query_trace")
            match_reason = rag_payload.get("match_reason") or rag_payload.get("selection_reason")

        lead_resolution = LeadResolution(
            status="found" if lead_record else status,
            lead_id=lead_record.get("id") if isinstance(lead_record, dict) else None,
            confidence=0.82 if lead_record else 0.25,
            source=lead_source if lead_source else ("rag" if lead_record else "rag_not_found"),
            alternatives=([{ "match_reason": match_reason }] if match_reason else []),
            lead_data=lead_record if isinstance(lead_record, dict) else None,
        )

        if lead_resolution_payload:
            try:
                if not lead_resolution.lead_id and lead_resolution_payload.get("lead_id"):
                    lead_resolution.lead_id = lead_resolution_payload.get("lead_id")
                if lead_resolution_payload.get("status"):
                    lead_resolution.status = lead_resolution_payload.get("status") or lead_resolution.status
                if lead_resolution_payload.get("lead_source") and not lead_resolution.source:
                    lead_resolution.source = lead_resolution_payload.get("lead_source")
                if lead_resolution_payload.get("match_reason") and not lead_resolution.alternatives:
                    lead_resolution.alternatives = [{"match_reason": lead_resolution_payload.get("match_reason")}]
                if not match_reason and lead_resolution_payload.get("match_reason"):
                    match_reason = lead_resolution_payload.get("match_reason")
            except Exception:
                # Avoid blocking reply packet on enrichment of optional payload
                pass

        convo_summary = None
        if conversations:
            latest = conversations[0]
            convo_summary = ConversationSummary(
                conversation_id=latest.get("id"),
                summary=latest.get("summary") or latest.get("topic"),
                recent_messages=messages[-10:] if isinstance(messages, list) else [],
                last_message_at=(messages[-1].get("created_at") if messages else None),
            )
        else:
            convo_summary = ConversationSummary(
                recent_messages=messages[-10:] if isinstance(messages, list) else [],
            )

        facts = Facts(
            first_name=lead_record.get("first_name") if isinstance(lead_record, dict) else None,
            last_name=lead_record.get("last_name") if isinstance(lead_record, dict) else None,
            # DB column is 'company_name'; also check 'company' for backward compat
            company=(lead_record.get("company_name") or lead_record.get("company")) if isinstance(lead_record, dict) else None,
            # DB column is 'job_title'; also check 'title'/'role' for backward compat
            role=(lead_record.get("job_title") or lead_record.get("title") or lead_record.get("role")) if isinstance(lead_record, dict) else None,
            email=lead_record.get("email") if isinstance(lead_record, dict) else email_event.get("from"),
            intent=email_event.get("intent") or email_event.get("subject"),
            extras={
                "email_event_subject": email_event.get("subject"),
                "goal": goal,
                "match_reason": match_reason,
            },
        )

        actions_taken = ActionsTaken(
            stored=bool(stored_ok),
            enriched=bool(lead_record or messages or conversations),
            writes=list(write_markers or []),
        )

        next_step = NextStep(
            delegate_to=["outbound"],
            reason="reply_packet_ready_for_outreach",
        )

        packet = ReplyPacket(
            lead_resolution=lead_resolution,
            conversation=convo_summary,
            facts=facts,
            actions_taken=actions_taken,
            inbound_email_event=email_event,
            recommended_strategy="craft personalized reply using retrieved history",
            next=next_step,
            query_trace=query_trace,
        )

        return packet.dict()
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check health of Leads Orchestrator.
        
        Returns:
            Health status
        """
        try:
            from tiers.tier_1.manager.deep_agent_factory import get_middleware_status
        except ImportError:
            # Fallback for migration phase
            from tiers.tier_1.manager.deep_agent_factory import get_middleware_status
        
        health = {
            "status": "healthy",
            "orchestrator": "leads",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {}
        }
        
        # Check Redis
        try:
            self.redis.ping()
            health["components"]["redis"] = {
                "status": "healthy",
                "tenant": self.tenant_id
            }
        except Exception as e:
            health["components"]["redis"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health["status"] = "degraded"
        
        # Check Deep Agent middleware
        try:
            middleware_status = get_middleware_status(self.agent)
            health["components"]["middleware"] = {
                "status": "healthy",
                **middleware_status
            }
        except Exception as e:
            health["components"]["middleware"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health["status"] = "degraded"
        
        # Check tools
        health["components"]["tools"] = {
            "status": "healthy",
            "count": len(self._build_tools()),
            "deterministic": 5,
            "delegation": 3
        }
        
        return health
