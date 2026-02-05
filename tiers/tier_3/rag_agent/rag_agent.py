"""
RAG Agent - Tier 3 Operational Agent

Deep Agent implementation for Retrieval Augmented Generation:
- Database retrieval from Supabase
- Schema-specific queries for leads, conversations, messages
- Vector search enrichment (optional)
- Validation and completeness scoring

Architecture:
- Layer 2: Deep Agent with TodoList, Filesystem, SubAgent middleware
- Layer 1: Wrapped in Agent Harness for production reliability
- Direct Supabase access (READ ONLY - no writes)
"""

import logging
import json
import uuid
import os
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
from langchain.tools import tool
from deepagents import create_deep_agent
import redis

# Optional OpenAI import for LLM-based repair
try:
    from openai import OpenAI  # type: ignore
except Exception:
    OpenAI = None  # type: ignore

# Import embeddings and vector DB with fallback pattern
try:
    from services.vector_db import VectorDBClient, EmbeddingsProvider
    from services.vector_db.pipeline import EmbeddingPipeline
except ImportError:
    VectorDBClient = None
    EmbeddingsProvider = None
    EmbeddingPipeline = None

# Import Supabase adapter for database retrieval
try:
    from services.persistence.adapters.supabase_adapter import SupabaseAdapter
except ImportError:
    SupabaseAdapter = None


class _ReadOnlyPersistenceAdapter:
    """Minimal facade that only exposes read/query operations.

    This is a defense-in-depth guardrail: even if someone accidentally adds a
    write-capable tool to RAG in the future, the underlying adapter will refuse
    any mutations.
    """

    def __init__(self, adapter: Any):
        self._adapter = adapter
        # Preserve capability metadata for planners/debugging where present.
        self.capabilities = getattr(adapter, "capabilities", {})

    def read(self, table: str, id_value: Any, id_column: str = "id") -> Any:
        return self._adapter.read(table=table, id_value=id_value, id_column=id_column)

    def query(
        self,
        table: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        order_by: Optional[str] = None,
        descending: bool = False,
        select: Optional[List[str]] = None,
    ) -> Any:
        return self._adapter.query(
            table=table,
            filters=filters,
            limit=limit,
            order_by=order_by,
            descending=descending,
            select=select,
        )

    def get_columns(self, table: str) -> Any:  # pragma: no cover
        return getattr(self._adapter, "get_columns")(table)

    def write(self, *_args: Any, **_kwargs: Any) -> Any:  # pragma: no cover
        raise PermissionError("RAG Agent is read-only: write is not allowed")

    def batch_write(self, *_args: Any, **_kwargs: Any) -> Any:  # pragma: no cover
        raise PermissionError("RAG Agent is read-only: batch_write is not allowed")

    def upsert(self, *_args: Any, **_kwargs: Any) -> Any:  # pragma: no cover
        raise PermissionError("RAG Agent is read-only: upsert is not allowed")

    def delete(self, *_args: Any, **_kwargs: Any) -> Any:  # pragma: no cover
        raise PermissionError("RAG Agent is read-only: delete is not allowed")

    def __getattr__(self, name: str) -> Any:  # pragma: no cover
        # Do not expose the underlying SDK client or other mutation paths.
        raise AttributeError(f"Attribute '{name}' is not available on read-only adapter")

# Import security module for prompt hardening
from core.security.prompt_hardening import get_hardened_internal_prompt

# Import entity schemas and validators
try:
    from config.rag_entities import EntityType
    from tiers.tier_3.rag_agent.validators import validate_entity_payload, get_validation_summary
except ImportError:
    EntityType = None
    validate_entity_payload = None
    get_validation_summary = None

logger = logging.getLogger(__name__)


class RAGAgent:
    """
    Tier 3: RAG Agent (Deep Agent)
    
    Responsibilities:
    - Retrieve leads and conversations from Supabase (READ ONLY)
    - Query staging_leads, leads, conversations, messages tables
    - Validate entity payloads with completeness scoring
    - Optional: Vector search for similar entities
    
    Tools:
    - Schema-specific retrieval tools (12 tools across 4 tables)
    - Validation tools
    - Optional: Vector search tools
    
    CRITICAL: This agent does NOT write to database or call external APIs.
    """
    
    def __init__(
        self,
        redis_client: redis.Redis,
        tenant_id: str = "default",
        model: str = "gpt-4o-mini"
    ):
        """
        Initialize RAG Agent with Deep Agent.
        
        Args:
            redis_client: Redis client for caching
            tenant_id: Tenant context for multi-tenant isolation
            model: OpenAI model (gpt-4o-mini for cost efficiency)
        """
        self.redis = redis_client
        self.tenant_id = tenant_id
        self.model = model
        self.use_langgraph = os.getenv("LANGGRAPH_WORKFLOWS_ENABLED", "1").lower() in ("1", "true", "yes")
        self._graph_runner = None
        
        # Initialize embedding pipeline (optional - for vector search)
        self.embedding_pipeline = None
        if EmbeddingPipeline:
            self.embedding_pipeline = EmbeddingPipeline(
                redis_client=redis_client,
                tenant_id=tenant_id
            )
        
        # Initialize Supabase adapter for database retrieval (READ ONLY)
        self.supabase = None
        if SupabaseAdapter:
            try:
                supabase_url = os.environ.get("SUPABASE_URL")
                rag_jwt = os.environ.get("SUPABASE_RAG_JWT")
                service_key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
                # Prefer dedicated RAG agent JWT (read-only), but fall back to service key if JWT auth is broken.
                supabase_key = rag_jwt or service_key
                supabase_anon_key = os.environ.get("SUPABASE_ANON_KEY")
                
                if not supabase_url or not supabase_key:
                    logger.warning("SUPABASE_URL/SUPABASE_RAG_JWT not configured - retrieval tools disabled")
                else:
                    # Validate custom JWT quickly; if it yields 401/403, fall back to service key.
                    # This prevents silent failures where RAG returns empty context due to auth.
                    if rag_jwt and supabase_anon_key and service_key:
                        try:
                            probe_url = f"{supabase_url.rstrip('/')}/rest/v1/staging_leads"
                            headers = {
                                "apikey": supabase_anon_key,
                                "Authorization": f"Bearer {rag_jwt}",
                                "Accept": "application/json",
                            }
                            resp = requests.get(probe_url, headers=headers, params={"select": "id", "limit": 1}, timeout=10)
                            if resp.status_code in (401, 403):
                                logger.warning(
                                    "Supabase custom JWT unauthorized (status=%s); falling back to service key for RAG reads. "
                                    "Fix by generating SUPABASE_RAG_JWT with your Supabase JWT secret.",
                                    resp.status_code,
                                )
                                rag_jwt = None
                                supabase_key = service_key
                        except Exception as e:
                            logger.warning(f"Supabase JWT probe failed; continuing with configured auth: {e}")

                    # If using custom JWT, pass anon_key for proper authentication
                    if rag_jwt and supabase_anon_key:
                        self.supabase = _ReadOnlyPersistenceAdapter(
                            SupabaseAdapter(supabase_url, supabase_key, anon_key=supabase_anon_key)
                        )
                        logger.info("Supabase adapter initialized (READ ONLY mode with custom JWT)")
                    else:
                        self.supabase = _ReadOnlyPersistenceAdapter(
                            SupabaseAdapter(supabase_url, supabase_key)
                        )
                        logger.info("Supabase adapter initialized (READ ONLY mode)")
            except Exception as e:
                logger.warning(f"Supabase adapter init failed: {e}")
        
        # Create Deep Agent with middleware
        self.agent = create_deep_agent(
            model=model,
            system_prompt=self._get_system_prompt(),
            tools=self._build_tools()
        )
        # TodoListMiddleware, FilesystemMiddleware, SubAgentMiddleware auto-configured
        
        logger.info(f"RAGAgent initialized (tenant={tenant_id}, model={model})")
    
    def _get_system_prompt(self) -> str:
                """System prompt defining RAG Agent role and decision framework"""
                base_prompt = f"""You are the RAG Agent - retrieval specialist for Supabase. READ ONLY.

**Use-case oriented tool guide**

Reply generation (preferred path)
    -> build_reply_context(email=?, thread_id?, subject?)
         * Finds lead across leads + staging_leads
         * Picks the right conversation (thread_id > subject > recency)
         * Returns ordered messages and other thread summaries

Lead lookup
    -> Quick: get_lead_context (cascading, single source)
    -> Full: get_unified_lead_context (parallel, both tables)

Conversation selection
    -> select_conversation(lead_id, lead_source, criteria="most_recent_inbound")
         criteria: most_recent_inbound | most_recent_any | open_only | by_thread_id | by_subject

Message history
    -> get_conversation_messages(conversation_id)
    -> get_latest_lead_replies(lead_id)

Search and enrichment
    -> search_leads / search_leads_by_enriched_data
    -> check_lead_enrichment_history

Staging workflows
    -> get_staging_leads_pending_enrichment / promotion_ready / get_staging_lead_by_id

Vector search (if available)
    -> vector_search_companies / semantic_search

**Decision rules**
1) If goal mentions reply/response -> build_reply_context
2) If goal mentions find/lookup lead -> get_lead_context or get_unified_lead_context
3) If goal mentions conversation choice -> select_conversation
4) If goal mentions all messages -> get_conversation_messages
5) Keep payloads small; include query_trace for debugging

Tenant: {self.tenant_id}
Current task: {{input}}
"""
                return get_hardened_internal_prompt(base_prompt)
    
    def _build_tools(self) -> List:
        """Build RAG retrieval tools - schema-specific queries for 4 core tables"""
        tools = [
            # Validation tool (existing)
            self._create_validate_entity_payload_tool(),
        ]
        
        # Add Supabase retrieval tools if adapter is available
        if self.supabase:
            # Staging Leads tools (3)
            tools.extend([
                self._create_get_staging_leads_pending_enrichment_tool(),
                self._create_get_staging_leads_promotion_ready_tool(),
                self._create_get_staging_lead_by_id_tool(),
            ])
            
            # Reply-first tools (preferred for responses)
            tools.extend([
                self._create_build_reply_context_tool(),
            ])

            # Lead context tools
            tools.extend([
                self._create_get_unified_lead_context_tool(),
                self._create_get_lead_context_tool(),
                self._create_get_lead_by_id_tool(),
                self._create_search_leads_tool(),
                self._create_search_leads_by_enriched_data_tool(),
                self._create_check_lead_enrichment_history_tool(),
            ])

            # Conversation selection and lookup
            tools.extend([
                self._create_select_conversation_tool(),
                self._create_get_lead_conversations_tool(),
                self._create_get_conversation_by_id_tool(),
            ])

            # Messages tools
            tools.extend([
                self._create_get_conversation_messages_tool(),
                self._create_get_latest_lead_replies_tool(),
            ])
        else:
            logger.warning("Supabase adapter not available - retrieval tools disabled")
        
        # Optional: Vector search tools (if embedding pipeline available)
        if self.embedding_pipeline:
            tools.extend([
                self._create_index_entity_tool(),
                self._create_retrieve_similar_entities_tool(),
                self._create_vector_search_companies_tool(),
                self._create_vector_search_leads_tool(),
                self._create_semantic_search_tool(),
            ])
        
        return tools
    
    # ==================== VALIDATION TOOLS (TIER 1) ====================
    
    def _create_validate_entity_payload_tool(self):
        """Tool for validating entity payloads (always first)"""
        
        @tool
        def validate_entity_payload_tool(
            entity_type: str,
            payload: dict
        ) -> dict:
            """
            Validate entity payload before processing.
            
            ALWAYS use this tool FIRST before attempting any enrichment.
            
            Args:
                entity_type: Type of entity (lead, conversation, message, campaign)
                payload: Entity data to validate
            
            Returns:
                {
                    "is_valid": bool,
                    "completeness_score": float (0.0-1.0),
                    "can_use_deterministic": bool,
                    "needs_repair": bool,
                    "errors": list,
                    "missing_required_fields": list
                }
            """
            if not validate_entity_payload or not EntityType:
                return {
                    "is_valid": False,
                    "error": "Validation system not available"
                }
            
            try:
                # Convert string to EntityType enum
                entity_enum = EntityType(entity_type.lower())
                
                # Validate payload
                result = validate_entity_payload(entity_enum, payload)
                
                # Log validation summary
                summary = get_validation_summary(result) if get_validation_summary else str(result)
                logger.info(f"Validation result:\n{summary}")
                
                # Return decision-ready format
                return {
                    "is_valid": result.is_valid,
                    "completeness_score": result.completeness_score,
                    "can_use_deterministic": result.can_use_deterministic(),
                    "needs_repair": result.needs_llm_repair(),
                    "is_hopeless": result.is_hopeless(),
                    "errors": [
                        {"field": e.field, "message": e.message}
                        for e in result.errors
                    ],
                    "warnings": [
                        {"field": w.field, "message": w.message}
                        for w in result.warnings
                    ],
                    "missing_required_fields": result.missing_required_fields,
                    "present_fields": sorted(list(result.present_fields))
                }
            except Exception as e:
                logger.error(f"Validation failed: {e}")
                return {
                    "is_valid": False,
                    "completeness_score": 0.0,
                    "error": str(e)
                }
        
        return validate_entity_payload_tool
    
    # ==================== DETERMINISTIC ENTITY TOOLS (TIER 2) ====================
    
    def _create_index_entity_tool(self):
        """Tool for indexing entities in vector DB"""
        
        @tool
        async def index_entity_tool(
            entity_type: str,
            record: dict
        ) -> dict:
            """
            Index entity in vector database for similarity search.
            
            Use ONLY when validation passes (completeness >= 0.7).
            
            Args:
                entity_type: Type of entity to index
                record: Full entity record with required fields
            
            Returns:
                {"success": bool, "vector_id": str}
            """
            if not self.embedding_pipeline:
                return {
                    "success": False,
                    "error": "Embedding pipeline not available"
                }
            
            try:
                entity_enum = EntityType(entity_type.lower())
                success = await self.embedding_pipeline.index_entity(entity_enum, record)
                
                record_id = record.get("id", "unknown")
                return {
                    "success": success,
                    "vector_id": f"{entity_type}:{record_id}",
                    "indexed_at": datetime.utcnow().isoformat()
                }
            except Exception as e:
                logger.error(f"Index entity failed: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
        
        return index_entity_tool
    
    def _create_retrieve_similar_entities_tool(self):
        """Tool for retrieving similar entities via vector search"""
        
        @tool
        async def retrieve_similar_entities_tool(
            entity_type: str,
            query: str,
            limit: int = 10,
            filters: str = "{}"
        ) -> dict:
            """
            Find similar entities using vector similarity search.
            
            Args:
                entity_type: Type of entity to search
                query: Natural language query
                limit: Max results (default 10)
                filters: JSON string of metadata filters (optional)
            
            Returns:
                {
                    "matches": [
                        {"record_id": str, "similarity_score": float, "metadata": dict}
                    ]
                }
            """
            if not self.embedding_pipeline:
                return {
                    "matches": [],
                    "error": "Embedding pipeline not available"
                }
            
            try:
                entity_enum = EntityType(entity_type.lower())
                filter_dict = json.loads(filters) if filters and filters != "{}" else None
                
                results = await self.embedding_pipeline.search_similar(
                    entity_type=entity_enum,
                    query=query,
                    limit=limit,
                    filters=filter_dict
                )
                
                return {
                    "matches": results,
                    "count": len(results),
                    "query": query
                }
            except Exception as e:
                logger.error(f"Similarity search failed: {e}")
                return {
                    "matches": [],
                    "error": str(e)
                }
        
        return retrieve_similar_entities_tool
    
    def _create_enrich_entity_tool(self):
        """Tool for multi-step entity enrichment"""
        crunchbase = self.crunchbase_client
        linkedin = self.linkedin_client
        
        @tool
        def enrich_entity_tool(
            entity_type: str,
            record: dict,
            include_funding: bool = True,
            include_social: bool = True
        ) -> dict:
            """
            Enrich entity with external data (Crunchbase, LinkedIn, etc).
            
            Use ONLY when validation passes. This is a multi-step pipeline.
            
            Args:
                entity_type: Type of entity to enrich
                record: Entity record to enrich
                include_funding: Get funding data (default True)
                include_social: Get social media data (default True)
            
            Returns:
                {
                    "enriched_data": dict,
                    "confidence": float,
                    "sources": list,
                    "enriched_fields": list
                }
            """
            logger.info(f"Enrich {entity_type}: {record.get('id', 'unknown')}")
            
            enriched_data = {}
            sources = []
            enriched_fields = []
            confidences = []
            
            # Extract company/person name from record
            company_name = record.get("company") or record.get("company_name") or record.get("organization")
            person_name = record.get("name") or (
                (record.get("first_name", "") + " " + record.get("last_name", "")).strip()
            )
            
            # 1. CrunchBase lookup for company data
            if company_name and crunchbase:
                try:
                    cb_result = crunchbase.lookup_company(company_name)
                    if cb_result.get("status") == "success":
                        enriched_data["company_info"] = {
                            "website": cb_result.get("website"),
                            "industry": cb_result.get("industry"),
                            "headquarters": cb_result.get("headquarters"),
                            "employee_count": cb_result.get("employee_count"),
                            "founded_date": cb_result.get("founded_date")
                        }
                        sources.append("crunchbase")
                        enriched_fields.append("company_info")
                        confidences.append(cb_result.get("confidence", 0.8))
                        
                        # Get funding if requested
                        if include_funding:
                            funding = crunchbase.get_funding_data(company_name)
                            if funding.get("status") == "success":
                                enriched_data["funding"] = {
                                    "total_funding": funding.get("total_funding"),
                                    "rounds_count": len(funding.get("funding_rounds", []))
                                }
                                enriched_fields.append("funding")
                                confidences.append(funding.get("confidence", 0.8))
                except Exception as e:
                    logger.warning(f"CrunchBase enrichment failed: {e}")
            
            # 2. LinkedIn lookup for social/professional data
            if include_social and linkedin:
                try:
                    if company_name:
                        li_result = linkedin.lookup_company(company_name)
                        if li_result.get("status") == "success":
                            enriched_data["linkedin_company"] = {
                                "linkedin_id": li_result.get("linkedin_id"),
                                "industry": li_result.get("industry"),
                                "company_size": li_result.get("company_size")
                            }
                            sources.append("linkedin")
                            enriched_fields.append("linkedin_company")
                            confidences.append(li_result.get("confidence", 0.7))
                    
                    if person_name and person_name.strip():
                        parts = person_name.split(" ", 1)
                        li_person = linkedin.lookup_person(
                            first_name=parts[0],
                            last_name=parts[1] if len(parts) > 1 else ""
                        )
                        if li_person.get("status") == "success":
                            enriched_data["linkedin_person"] = {
                                "linkedin_id": li_person.get("linkedin_id"),
                                "headline": li_person.get("headline")
                            }
                            if "linkedin" not in sources:
                                sources.append("linkedin")
                            enriched_fields.append("linkedin_person")
                            confidences.append(li_person.get("confidence", 0.7))
                except Exception as e:
                    logger.warning(f"LinkedIn enrichment failed: {e}")
            
            # Calculate aggregate confidence
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            return {
                "status": "completed" if enriched_fields else "no_data",
                "enriched_data": enriched_data,
                "confidence": round(avg_confidence, 2),
                "sources": sources,
                "enriched_fields": enriched_fields
            }
        
        return enrich_entity_tool
    
    # ==================== LLM REPAIR TOOLS (TIER 3) ====================
    
    def _create_repair_entity_data_tool(self):
        """Tool for repairing malformed entity data using LLM reasoning"""
        
        @tool
        def repair_entity_data_tool(
            entity_type: str,
            partial_payload: dict,
            context: dict = None
        ) -> dict:
            """
            Repair malformed or incomplete entity data using LLM reasoning.
            
            Use ONLY when:
            - completeness_score between 0.3 and 0.7
            - needs_repair = true from validation
            
            Max 2 repair attempts per payload.
            
            Args:
                entity_type: Type of entity to repair
                partial_payload: Incomplete/malformed data
                context: Additional context from envelope metadata
            
            Returns:
                {
                    "repaired_payload": dict,
                    "repair_strategy": str,
                    "confidence": float,
                    "repaired_fields": list
                }
            """
            logger.info(f"Repair {entity_type} data: {list(partial_payload.keys())}")

            context = context or {}
            repaired_payload = dict(partial_payload or {})
            repaired_fields: List[str] = []

            def _set_if_missing(key: str, value: Optional[str]) -> None:
                if key not in repaired_payload or repaired_payload.get(key) in (None, ""):
                    if value not in (None, ""):
                        repaired_payload[key] = value
                        repaired_fields.append(key)

            def _extract_domain(raw: Optional[str]) -> Optional[str]:
                if not raw:
                    return None
                value = str(raw).strip().lower()
                if value.startswith("http"):
                    value = value.split("//", 1)[-1]
                if "/" in value:
                    value = value.split("/", 1)[0]
                if "@" in value:
                    value = value.split("@", 1)[-1]
                return value or None

            # Heuristic repairs (no LLM)
            name = repaired_payload.get("name")
            if name and (not repaired_payload.get("first_name") or not repaired_payload.get("last_name")):
                parts = str(name).strip().split(" ", 1)
                _set_if_missing("first_name", parts[0])
                if len(parts) > 1:
                    _set_if_missing("last_name", parts[1])

            first = repaired_payload.get("first_name")
            last = repaired_payload.get("last_name")
            if not repaired_payload.get("name") and (first or last):
                full_name = " ".join([p for p in [first, last] if p])
                _set_if_missing("name", full_name)

            company_name = repaired_payload.get("company") or repaired_payload.get("company_name") or repaired_payload.get("organization")
            _set_if_missing("company", company_name)

            domain = (
                _extract_domain(repaired_payload.get("company_domain"))
                or _extract_domain(repaired_payload.get("company_website"))
                or _extract_domain(context.get("company_domain"))
                or _extract_domain(context.get("company_website"))
            )

            if not repaired_payload.get("email") and first and last and domain:
                email = f"{str(first).strip().lower()}.{str(last).strip().lower()}@{domain}"
                email = email.replace(" ", "")
                _set_if_missing("email", email)

            llm_enabled = os.getenv("RAG_LLM_REPAIR_ENABLED", "1").lower() in ("1", "true", "yes")
            if llm_enabled and OpenAI and os.getenv("OPENAI_API_KEY"):
                try:
                    missing_required_fields: List[str] = []
                    if validate_entity_payload and EntityType:
                        try:
                            entity_enum = EntityType(entity_type.lower())
                            validation = validate_entity_payload(entity_enum, repaired_payload)
                            missing_required_fields = validation.missing_required_fields
                        except Exception:
                            missing_required_fields = []

                    system_prompt = (
                        "You are a data repair assistant. Return ONLY valid JSON. "
                        "Fill missing fields using context and available data; do NOT hallucinate. "
                        "Do not modify existing non-empty fields."
                    )
                    user_prompt = {
                        "entity_type": entity_type,
                        "partial_payload": repaired_payload,
                        "missing_required_fields": missing_required_fields,
                        "context": context,
                        "output_format": {
                            "repaired_payload": "object",
                            "repaired_fields": "list of strings",
                            "repair_strategy": "llm",
                            "confidence": "0.0-1.0"
                        },
                    }

                    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                    model = os.getenv("RAG_LLM_REPAIR_MODEL", "gpt-4o-mini")
                    temperature = float(os.getenv("RAG_LLM_REPAIR_TEMPERATURE", "0"))

                    completion = client.chat.completions.create(
                        model=model,
                        temperature=temperature,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": json.dumps(user_prompt)},
                        ],
                        response_format={"type": "json_object"},
                    )

                    content = completion.choices[0].message.content if completion.choices else "{}"
                    data = json.loads(content) if content else {}
                    llm_payload = data.get("repaired_payload") or {}

                    # Only fill missing/empty fields from LLM output
                    for key, value in llm_payload.items():
                        if repaired_payload.get(key) in (None, "") and value not in (None, ""):
                            repaired_payload[key] = value
                            if key not in repaired_fields:
                                repaired_fields.append(key)

                    return {
                        "repaired_payload": repaired_payload,
                        "repair_strategy": data.get("repair_strategy", "llm"),
                        "confidence": float(data.get("confidence", 0.5 if repaired_fields else 0.0)),
                        "repaired_fields": repaired_fields,
                    }
                except Exception as e:
                    logger.warning(f"LLM repair failed, falling back to heuristics: {e}")

            return {
                "repaired_payload": repaired_payload,
                "repair_strategy": "heuristic",
                "confidence": 0.2 if repaired_fields else 0.0,
                "repaired_fields": repaired_fields,
            }
        
        return repair_entity_data_tool
    
    # ==================== SUPABASE RETRIEVAL TOOLS ====================
    # 12 schema-specific tools across 4 core tables
    
    # --- STAGING LEADS TOOLS (3) ---
    
    def _create_get_staging_leads_pending_enrichment_tool(self):
        """Get staging leads pending enrichment (FIFO queue)"""
        supabase = self.supabase
        
        @tool
        def get_staging_leads_pending_enrichment(limit: int = 50) -> Dict[str, Any]:
            """
            Get staging leads that need enrichment (FIFO queue).
            
            Returns oldest leads first where validation_status is null/incomplete.
            
            Args:
                limit: Max records to return (default 50, max 500)
            
            Returns:
                {"status": "success", "records": [...], "count": int}
            """
            try:
                limit = min(limit, 500)  # Hard cap
                
                result = supabase.query(
                    table="staging_leads",
                    filters={"validation_status": None},  # Pending enrichment
                    limit=limit,
                    order_by="created_at",
                    descending=False  # FIFO: oldest first
                )
                
                return {
                    "status": "success",
                    "records": result.get("data", []),
                    "count": len(result.get("data", []))
                }
            except Exception as e:
                logger.error(f"Get pending staging leads failed: {e}")
                return {"status": "error", "error": str(e)}
        
        return get_staging_leads_pending_enrichment
    
    def _create_get_staging_leads_promotion_ready_tool(self):
        """Get staging leads ready to promote to leads table"""
        supabase = self.supabase
        
        @tool
        def get_staging_leads_promotion_ready(limit: int = 50) -> Dict[str, Any]:
            """
            Get staging leads that passed validation and are ready to promote.
            
            Returns leads with validation_status='complete' and completeness_score >= 0.7.
            
            Args:
                limit: Max records to return (default 50, max 500)
            
            Returns:
                {"status": "success", "records": [...], "count": int}
            """
            try:
                limit = min(limit, 500)
                
                # Query all complete leads, filter score in Python (JSONB limitation)
                result = supabase.query(
                    table="staging_leads",
                    filters={"validation_status": "complete"},
                    limit=500,  # Get pool for filtering
                    order_by="created_at",
                    descending=False
                )
                
                # Python-side filter for completeness_score >= 0.7
                all_leads = result.get("data", [])
                promotion_ready = [
                    lead for lead in all_leads
                    if lead.get("completeness_score", 0.0) >= 0.7
                ][:limit]
                
                return {
                    "status": "success",
                    "records": promotion_ready,
                    "count": len(promotion_ready)
                }
            except Exception as e:
                logger.error(f"Get promotion-ready leads failed: {e}")
                return {"status": "error", "error": str(e)}
        
        return get_staging_leads_promotion_ready
    
    def _create_get_staging_lead_by_id_tool(self):
        """Get single staging lead by ID"""
        supabase = self.supabase
        
        @tool
        def get_staging_lead_by_id(lead_id: str) -> Dict[str, Any]:
            """
            Get single staging lead by ID.
            
            Args:
                lead_id: UUID of staging lead
            
            Returns:
                {"status": "success", "record": {...}} or {"status": "not_found"}
            """
            try:
                result = supabase.read(table="staging_leads", id_value=lead_id)
                
                if result.get("data"):
                    return {
                        "status": "success",
                        "record": result["data"]
                    }
                else:
                    return {"status": "not_found", "lead_id": lead_id}
            except Exception as e:
                logger.error(f"Get staging lead by ID failed: {e}")
                return {"status": "error", "error": str(e)}
        
        return get_staging_lead_by_id
    
    # --- LEADS TOOLS (4) ---
    
    def _create_search_leads_tool(self):
        """Search leads by standard fields"""
        supabase = self.supabase
        
        @tool
        def search_leads(
            email: str = None,
            company: str = None,
            title: str = None,
            status: str = None,
            min_score: float = None,
            campaign_id: str = None,
            limit: int = 50
        ) -> Dict[str, Any]:
            """
            Search leads by standard fields (non-JSONB).
            
            All parameters are optional - combines with AND logic.
            
            Args:
                email: Email address (exact match)
                company: Company name (exact match)
                title: Job title (exact match)
                status: Lead status (active, contacted, converted, etc.)
                min_score: Minimum qualification score (0-100)
                campaign_id: Campaign UUID
                limit: Max records (default 50, max 500)
            
            Returns:
                {"status": "success", "records": [...], "count": int}
            """
            try:
                limit = min(limit, 500)
                
                # Build filters from provided params
                filters = {}
                if email:
                    filters["email"] = email
                if company:
                    filters["company"] = company
                if title:
                    filters["title"] = title
                if status:
                    filters["status"] = status
                if campaign_id:
                    filters["campaign_id"] = campaign_id
                
                # Query with filters
                result = supabase.query(
                    table="leads",
                    filters=filters,
                    limit=limit,
                    order_by="created_at",
                    descending=True
                )
                
                all_leads = result.get("data", [])
                
                # Python-side filter for min_score (if provided)
                if min_score is not None:
                    all_leads = [
                        lead for lead in all_leads
                        if lead.get("qualification_score", 0) >= min_score
                    ]
                
                return {
                    "status": "success",
                    "records": all_leads,
                    "count": len(all_leads)
                }
            except Exception as e:
                logger.error(f"Search leads failed: {e}")
                return {"status": "error", "error": str(e)}
        
        return search_leads
    
    def _create_search_leads_by_enriched_data_tool(self):
        """Search leads by JSONB enriched data fields"""
        supabase = self.supabase
        
        @tool
        def search_leads_by_enriched_data(
            industry: str = None,
            funding_stage: str = None,
            min_employee_count: int = None,
            max_employee_count: int = None,
            location: str = None,
            limit: int = 50
        ) -> Dict[str, Any]:
            """
            Search leads by enriched data (JSONB fields in raw_data).
            
            NOTE: Requires Python-side filtering due to adapter JSONB limitations.
            Queries up to 500 records and filters in memory.
            
            Args:
                industry: Industry/sector (e.g., "SaaS", "FinTech")
                funding_stage: Funding stage (e.g., "Series A", "Seed")
                min_employee_count: Minimum employee count
                max_employee_count: Maximum employee count
                location: Location/city
                limit: Max records (default 50, max 500)
            
            Returns:
                {"status": "success", "records": [...], "count": int}
            """
            try:
                limit = min(limit, 500)
                
                # Query broader pool (up to 500) for Python-side filtering
                result = supabase.query(
                    table="leads",
                    filters={},  # No SQL filters - get all
                    limit=500,
                    order_by="created_at",
                    descending=True
                )
                
                all_leads = result.get("data", [])
                
                # Python-side JSONB filtering
                filtered_leads = []
                for lead in all_leads:
                    raw_data = lead.get("raw_data", {})
                    if not isinstance(raw_data, dict):
                        continue
                    
                    # Check each filter
                    if industry and raw_data.get("industry") != industry:
                        continue
                    if funding_stage and raw_data.get("funding_stage") != funding_stage:
                        continue
                    if min_employee_count and raw_data.get("employee_count", 0) < min_employee_count:
                        continue
                    if max_employee_count and raw_data.get("employee_count", float('inf')) > max_employee_count:
                        continue
                    if location and location.lower() not in str(raw_data.get("location", "")).lower():
                        continue
                    
                    filtered_leads.append(lead)
                    if len(filtered_leads) >= limit:
                        break
                
                return {
                    "status": "success",
                    "records": filtered_leads,
                    "count": len(filtered_leads)
                }
            except Exception as e:
                logger.error(f"Search enriched data failed: {e}")
                return {"status": "error", "error": str(e)}
        
        return search_leads_by_enriched_data
    
    def _create_check_lead_enrichment_history_tool(self):
        """Check if lead was previously enriched (avoid duplicate API calls)"""
        supabase = self.supabase
        
        @tool
        def check_lead_enrichment_history(lead_id: str) -> Dict[str, Any]:
            """
            Check enrichment history for a lead to avoid duplicate API calls.
            
            Examines raw_data JSONB field for enrichment metadata (sources, timestamps).
            
            Args:
                lead_id: Lead UUID
            
            Returns:
                {
                    "status": "success",
                    "enriched": bool,
                    "sources": ["crunchbase", "linkedin", ...],
                    "last_enriched_at": "ISO timestamp",
                    "raw_data_keys": [...]
                }
            """
            try:
                result = supabase.read(table="leads", id_value=lead_id)
                
                if not result.get("data"):
                    return {"status": "not_found", "lead_id": lead_id}
                
                lead = result["data"]
                raw_data = lead.get("raw_data", {})
                
                # Extract enrichment metadata
                enriched = bool(raw_data and isinstance(raw_data, dict) and len(raw_data) > 0)
                sources = []
                last_enriched_at = None
                
                # Check for known source keys
                if isinstance(raw_data, dict):
                    if "crunchbase" in raw_data or "crunchbase_data" in raw_data:
                        sources.append("crunchbase")
                    if "linkedin" in raw_data or "linkedin_data" in raw_data:
                        sources.append("linkedin")
                    
                    # Check for enrichment timestamp
                    last_enriched_at = raw_data.get("enriched_at") or raw_data.get("last_enriched_at")
                
                return {
                    "status": "success",
                    "enriched": enriched,
                    "sources": sources,
                    "last_enriched_at": last_enriched_at,
                    "raw_data_keys": list(raw_data.keys()) if isinstance(raw_data, dict) else []
                }
            except Exception as e:
                logger.error(f"Check enrichment history failed: {e}")
                return {"status": "error", "error": str(e)}
        
        return check_lead_enrichment_history
    
    def _create_get_lead_by_id_tool(self):
        """Get single lead by ID"""
        supabase = self.supabase
        
        @tool
        def get_lead_by_id(lead_id: str) -> Dict[str, Any]:
            """
            Get single lead by ID with all fields.
            
            Args:
                lead_id: Lead UUID
            
            Returns:
                {"status": "success", "record": {...}} or {"status": "not_found"}
            """
            try:
                result = supabase.read(table="leads", id_value=lead_id)
                
                if result.get("data"):
                    return {
                        "status": "success",
                        "record": result["data"]
                    }
                else:
                    return {"status": "not_found", "lead_id": lead_id}
            except Exception as e:
                logger.error(f"Get lead by ID failed: {e}")
                return {"status": "error", "error": str(e)}
        
        return get_lead_by_id

    def _create_get_lead_context_tool(self):
        """Get lead + conversations + messages using cascading table strategy."""
        supabase = self.supabase

        @tool
        def get_lead_context(
            email: Optional[str] = None,
            lead_id: Optional[str] = None,
            conversation_limit: int = 5,
            message_limit: int = 50,
        ) -> Dict[str, Any]:
            """
            Fetch lead record plus recent conversations and messages.

            Uses CASCADING QUERY STRATEGY:
            1. Email lookup: leads → staging_leads (fallback)
            2. lead_id lookup: leads → staging_leads (fallback)
            3. Enrichment: conversations → messages (from latest conversation)

            Args:
                email: Lead email (preferred lookup key)
                lead_id: Lead id (fallback/alternative)
                conversation_limit: Max conversations (default 5)
                message_limit: Max messages from the latest conversation (default 50)

            Returns:
                {
                    "status": "success" | "not_found" | "error",
                    "lead": {...} or None,
                    "lead_source": "leads" | "staging_leads" | None,
                    "conversations": [...],
                    "messages": [...],
                    "query_trace": {
                        "steps": [...],  # Each table queried with results
                        "fallback_used": bool,
                        "primary_table_hit": str | None
                    }
                }
            """
            if not supabase:
                return {"status": "error", "error": "supabase adapter unavailable"}

            try:
                from .query_strategy import cascading_lead_lookup

                result = cascading_lead_lookup(
                    adapter=supabase,
                    email=email,
                    lead_id=lead_id,
                    conversation_limit=conversation_limit,
                    message_limit=message_limit,
                )
                return result

            except ImportError as e:
                # Fallback to legacy single-table lookup if module not available
                logger.warning(f"query_strategy import failed, using legacy lookup: {e}")
                return self._legacy_get_lead_context(
                    supabase, email, lead_id, conversation_limit, message_limit
                )
            except Exception as e:
                logger.error(f"Get lead context failed: {e}")
                return {"status": "error", "error": str(e)}

        return get_lead_context

    def _legacy_get_lead_context(
        self,
        supabase,
        email: Optional[str],
        lead_id: Optional[str],
        conversation_limit: int,
        message_limit: int,
    ) -> Dict[str, Any]:
        """Legacy single-table lookup (fallback if query_strategy unavailable)."""
        try:
            lead_record = None
            if email:
                lead_res = supabase.query(table="leads", filters={"email": email}, limit=1)
                records = lead_res.get("data", []) if isinstance(lead_res, dict) else []
                if records:
                    lead_record = records[0]
            if lead_record is None and lead_id:
                res = supabase.read(table="leads", id_value=lead_id, id_column="id")
                lead_record = res.get("data") if isinstance(res, dict) else None

            conversations: List[Dict[str, Any]] = []
            messages: List[Dict[str, Any]] = []

            if lead_record:
                lead_id_val = lead_record.get("id")
                convo_res = supabase.query(
                    table="conversations",
                    filters={"lead_id": lead_id_val} if lead_id_val else {},
                    limit=max(1, min(conversation_limit, 25)),
                    order_by="created_at",
                    descending=True,
                )
                conversations = convo_res.get("data", []) if isinstance(convo_res, dict) else []

                if conversations:
                    latest_conv = conversations[0]
                    conv_id = latest_conv.get("id")
                    if conv_id:
                        msg_res = supabase.query(
                            table="messages",
                            filters={"conversation_id": conv_id},
                            limit=max(1, min(message_limit, 200)),
                            order_by="created_at",
                            descending=False,
                        )
                        messages = msg_res.get("data", []) if isinstance(msg_res, dict) else []

            return {
                "status": "success" if lead_record else "not_found",
                "lead": lead_record,
                "lead_source": "leads" if lead_record else None,
                "conversations": conversations,
                "messages": messages,
                "query_trace": {"note": "legacy_single_table_lookup"},
            }
        except Exception as e:
            logger.error(f"Legacy get lead context failed: {e}")
            return {"status": "error", "error": str(e)}

    def _create_get_unified_lead_context_tool(self):
        """
        Dynamic parallel search across leads AND staging_leads.

        Unlike get_lead_context (which stops at first hit), this tool:
        - Searches BOTH tables simultaneously
        - Returns ALL conversations from ALL sources
        - Lets the agent decide which conversation is most relevant
        """
        supabase = self.supabase

        @tool
        def get_unified_lead_context(
            email: Optional[str] = None,
            lead_id: Optional[str] = None,
            conversation_limit: int = 10,
            message_limit: int = 50,
        ) -> Dict[str, Any]:
            """
            Get comprehensive lead context from BOTH leads and staging_leads tables.

            Use this tool when you need to:
            - See ALL conversation history across qualification stages
            - Decide which conversation is most relevant for a reply
            - Get full context before generating a reply packet
            """
            if not supabase:
                return {"status": "error", "error": "supabase adapter unavailable"}

            try:
                from .query_strategy import unified_lead_context

                return unified_lead_context(
                    adapter=supabase,
                    email=email,
                    lead_id=lead_id,
                    conversation_limit=conversation_limit,
                    message_limit=message_limit,
                )
            except ImportError as e:
                logger.error(f"unified_lead_context import failed: {e}")
                return {"status": "error", "error": f"unified_lead_context unavailable: {e}"}
            except Exception as e:
                logger.error(f"Unified lead context failed: {e}")
                return {"status": "error", "error": str(e)}

        return get_unified_lead_context

    def _create_build_reply_context_tool(self):
        """Primary reply-generation retrieval tool."""
        supabase = self.supabase

        @tool
        def build_reply_context(
            email: Optional[str] = None,
            lead_id: Optional[str] = None,
            thread_id: Optional[str] = None,
            subject: Optional[str] = None,
            max_messages: int = 20,
        ) -> Dict[str, Any]:
            """Assemble full context for replies (lead + conversation + messages)."""
            if not supabase:
                return {"status": "error", "error": "supabase adapter unavailable"}

            try:
                from .strategies.reply_context import build_reply_context as _build

                return _build(
                    adapter=supabase,
                    email=email,
                    lead_id=lead_id,
                    thread_id=thread_id,
                    subject=subject,
                    max_messages=max_messages,
                    include_lead_profile=True,
                    include_all_threads=True,
                )
            except ImportError as e:
                logger.error(f"reply_context import failed: {e}")
                return {"status": "error", "error": str(e)}
            except Exception as e:
                logger.error(f"build_reply_context failed: {e}")
                return {"status": "error", "error": str(e)}

        return build_reply_context

    def _create_select_conversation_tool(self):
        """Pick the most relevant conversation for a known lead."""
        supabase = self.supabase

        @tool
        def select_conversation(
            lead_id: str,
            lead_source: str = "leads",
            criteria: str = "most_recent_inbound",
            thread_id: Optional[str] = None,
            subject: Optional[str] = None,
        ) -> Dict[str, Any]:
            """Select a conversation by criteria (thread_id > subject > recency)."""
            if not supabase:
                return {"status": "error", "error": "supabase adapter unavailable"}

            try:
                from .strategies.conversation_selection import get_relevant_conversation

                return get_relevant_conversation(
                    adapter=supabase,
                    lead_id=lead_id,
                    lead_source=lead_source,
                    selection_criteria=criteria,
                    context={"thread_id": thread_id, "subject": subject},
                )
            except ImportError as e:
                return {"status": "error", "error": str(e)}
            except Exception as e:
                return {"status": "error", "error": str(e)}

        return select_conversation
    
    # --- CONVERSATIONS TOOLS (2) ---
    
    def _create_get_lead_conversations_tool(self):
        """Get all conversations for a lead"""
        supabase = self.supabase
        
        @tool
        def get_lead_conversations(lead_id: str, limit: int = 50) -> Dict[str, Any]:
            """
            Get all conversations (email threads) for a lead.
            
            Args:
                lead_id: Lead UUID
                limit: Max conversations (default 50, max 100)
            
            Returns:
                {"status": "success", "records": [...], "count": int}
            """
            try:
                limit = min(limit, 100)
                
                result = supabase.query(
                    table="conversations",
                    filters={"lead_id": lead_id},
                    limit=limit,
                    order_by="created_at",
                    descending=True
                )
                
                conversations = result.get("data", [])
                
                # Enrich with message counts (optional)
                for conv in conversations:
                    conv_id = conv.get("id")
                    if conv_id:
                        msg_result = supabase.query(
                            table="messages",
                            filters={"conversation_id": conv_id},
                            limit=1000  # Count all messages
                        )
                        conv["message_count"] = len(msg_result.get("data", []))
                
                return {
                    "status": "success",
                    "records": conversations,
                    "count": len(conversations)
                }
            except Exception as e:
                logger.error(f"Get lead conversations failed: {e}")
                return {"status": "error", "error": str(e)}
        
        return get_lead_conversations
    
    def _create_get_conversation_by_id_tool(self):
        """Get single conversation by ID"""
        supabase = self.supabase
        
        @tool
        def get_conversation_by_id(conversation_id: str) -> Dict[str, Any]:
            """
            Get single conversation by ID.
            
            Args:
                conversation_id: Conversation UUID
            
            Returns:
                {"status": "success", "record": {...}} or {"status": "not_found"}
            """
            try:
                result = supabase.read(table="conversations", id_value=conversation_id)
                
                if result.get("data"):
                    conversation = result["data"]
                    
                    # Enrich with message count
                    msg_result = supabase.query(
                        table="messages",
                        filters={"conversation_id": conversation_id},
                        limit=1000
                    )
                    conversation["message_count"] = len(msg_result.get("data", []))
                    
                    return {
                        "status": "success",
                        "record": conversation
                    }
                else:
                    return {"status": "not_found", "conversation_id": conversation_id}
            except Exception as e:
                logger.error(f"Get conversation by ID failed: {e}")
                return {"status": "error", "error": str(e)}
        
        return get_conversation_by_id
    
    # --- MESSAGES TOOLS (2) ---
    
    def _create_get_conversation_messages_tool(self):
        """Get all messages in a conversation"""
        supabase = self.supabase
        
        @tool
        def get_conversation_messages(conversation_id: str, limit: int = 100) -> Dict[str, Any]:
            """
            Get all messages in a conversation (chronological order).
            
            Args:
                conversation_id: Conversation UUID
                limit: Max messages (default 100, max 500)
            
            Returns:
                {"status": "success", "records": [...], "count": int}
            """
            try:
                limit = min(limit, 500)
                
                result = supabase.query(
                    table="messages",
                    filters={"conversation_id": conversation_id},
                    limit=limit,
                    order_by="created_at",
                    descending=False  # Chronological: oldest first
                )
                
                return {
                    "status": "success",
                    "records": result.get("data", []),
                    "count": len(result.get("data", []))
                }
            except Exception as e:
                logger.error(f"Get conversation messages failed: {e}")
                return {"status": "error", "error": str(e)}
        
        return get_conversation_messages
    
    def _create_get_latest_lead_replies_tool(self):
        """Get latest lead replies across all conversations"""
        supabase = self.supabase
        
        @tool
        def get_latest_lead_replies(lead_id: str, limit: int = 10) -> Dict[str, Any]:
            """
            Get latest replies FROM the lead (not TO the lead).
            
            Useful for sentiment analysis, response monitoring.
            
            Args:
                lead_id: Lead UUID
                limit: Max messages (default 10, max 50)
            
            Returns:
                {"status": "success", "records": [...], "count": int}
            """
            try:
                limit = min(limit, 50)
                
                # First, get all conversation IDs for this lead
                conv_result = supabase.query(
                    table="conversations",
                    filters={"lead_id": lead_id},
                    limit=100
                )

                conversations = conv_result if isinstance(conv_result, list) else conv_result.get("data", []) if isinstance(conv_result, dict) else []
                conversation_ids = [c.get("id") for c in conversations if isinstance(c, dict) and c.get("id")]
                
                if not conversation_ids:
                    return {"status": "success", "records": [], "count": 0}
                
                # Get messages from these conversations where direction = "inbound" (from lead)
                all_messages = []
                for conv_id in conversation_ids:
                    msg_result = supabase.query(
                        table="messages",
                        filters={"conversation_id": conv_id, "sender_type": "lead"},
                        limit=500,
                        order_by="created_at",
                        descending=True,
                    )

                    msgs = msg_result if isinstance(msg_result, list) else msg_result.get("data", []) if isinstance(msg_result, dict) else []
                    all_messages.extend([m for m in msgs if isinstance(m, dict)])
                
                # Sort by created_at descending (latest first)
                all_messages.sort(key=lambda m: m.get("created_at", ""), reverse=True)
                
                return {
                    "status": "success",
                    "records": all_messages[:limit],
                    "count": len(all_messages[:limit])
                }
            except Exception as e:
                logger.error(f"Get latest lead replies failed: {e}")
                return {"status": "error", "error": str(e)}
        
        return get_latest_lead_replies
    
    # ==================== VECTOR SEARCH TOOLS (LEGACY) ====================
    
    def _create_vector_search_companies_tool(self):
        """Tool for vector search of similar companies"""
        
        @tool
        async def vector_search_companies(
            query: str,
            limit: int = 10
        ) -> Dict[str, Any]:
            """
            Search for similar companies using vector embeddings.
            
            Args:
                query: Company description or name
                limit: Maximum results to return (default: 10)
            
            Returns:
                Dict with matched companies and similarity scores
            """
            try:
                if not self.embedding_pipeline or not EntityType:
                    return {
                        "status": "error",
                        "error": "Embedding pipeline not available",
                        "confidence": 0.0,
                    }

                logger.info(f"Vector search companies: query='{query}', limit={limit}")
                results = await self.embedding_pipeline.search_similar(
                    entity_type=EntityType.CLIENT,
                    query=query,
                    limit=limit,
                )
                confidence = max((r.get("similarity_score", 0.0) for r in results), default=0.0)
                return {
                    "status": "success",
                    "query": query,
                    "matches": results,
                    "total": len(results),
                    "confidence": confidence,
                }
            except Exception as e:
                logger.error(f"Vector search failed: {e}")
                return {
                    "status": "error",
                    "error": str(e),
                    "confidence": 0.0
                }
        
        return vector_search_companies
    
    def _create_vector_search_leads_tool(self):
        """Tool for vector search of similar leads"""
        
        @tool
        async def vector_search_leads(
            query: str,
            limit: int = 10
        ) -> Dict[str, Any]:
            """
            Search for similar leads using vector embeddings.
            
            Args:
                query: Lead description or criteria
                limit: Maximum results to return (default: 10)
            
            Returns:
                Dict with matched leads and similarity scores
            """
            try:
                if not self.embedding_pipeline or not EntityType:
                    return {
                        "status": "error",
                        "error": "Embedding pipeline not available",
                        "confidence": 0.0,
                    }

                logger.info(f"Vector search leads: query='{query}', limit={limit}")
                results = await self.embedding_pipeline.search_similar(
                    entity_type=EntityType.LEAD,
                    query=query,
                    limit=limit,
                )
                confidence = max((r.get("similarity_score", 0.0) for r in results), default=0.0)
                return {
                    "status": "success",
                    "query": query,
                    "matches": results,
                    "total": len(results),
                    "confidence": confidence,
                }
            except Exception as e:
                logger.error(f"Vector search failed: {e}")
                return {
                    "status": "error",
                    "error": str(e),
                    "confidence": 0.0
                }
        
        return vector_search_leads
    
    def _create_semantic_search_tool(self):
        """Tool for semantic search across knowledge base"""
        
        @tool
        async def semantic_search(
            query: str,
            limit: int = 5
        ) -> Dict[str, Any]:
            """
            Semantic search for relevant information.
            
            Args:
                query: Search query
                limit: Maximum results (default: 5)
            
            Returns:
                Dict with relevant documents and relevance scores
            """
            try:
                if not self.embedding_pipeline or not self.embedding_pipeline.vector_db:
                    return {
                        "status": "error",
                        "error": "Embedding pipeline not available",
                        "confidence": 0.0,
                    }

                logger.info(f"Semantic search: query='{query}', limit={limit}")
                query_embedding = await self.embedding_pipeline.generate_embedding(query)
                if not query_embedding:
                    return {
                        "status": "error",
                        "error": "Failed to generate query embedding",
                        "confidence": 0.0,
                    }

                raw_results = self.embedding_pipeline.vector_db.semantic_search(
                    query_embedding=query_embedding,
                    limit=limit,
                )
                results = [
                    {
                        "id": r.id,
                        "score": r.score,
                        "metadata": r.metadata,
                        "text": r.text,
                    }
                    for r in raw_results
                ]
                confidence = max((r["score"] for r in results), default=0.0)
                return {
                    "status": "success",
                    "query": query,
                    "results": results,
                    "total": len(results),
                    "confidence": confidence,
                }
            except Exception as e:
                logger.error(f"Semantic search failed: {e}")
                return {
                    "status": "error",
                    "error": str(e),
                    "confidence": 0.0
                }
        
        return semantic_search
    
    # ==================== EXECUTION METHODS ====================
    
    def _get_graph_runner(self):
        if self._graph_runner is not None:
            return self._graph_runner
        from core.langgraph import LangGraphRunner

        async def _execute_graph(state):
            task_data_or_goal = state.get("task_data_or_goal")
            context = state.get("context") or {}
            return await self._execute_core(task_data_or_goal, context)

        async def _guardrails(state):
            output = state.get("output") or {}
            if output.get("status") == "error":
                return output
            return output

        self._graph_runner = LangGraphRunner(
            name="rag",
            execute_fn=_execute_graph,
            required_input_keys=["task_data_or_goal"],
            guardrails_fn=_guardrails,
        )
        return self._graph_runner

    async def execute(self, task_data_or_goal, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if self.use_langgraph:
            runner = self._get_graph_runner()
            graph_result = await runner.run(
                state_input={
                    "task_data_or_goal": task_data_or_goal,
                    "context": context or {},
                    "task_id": getattr(task_data_or_goal, "get", lambda _k=None: None)("task_id") if isinstance(task_data_or_goal, dict) else None,
                    "correlation_id": getattr(task_data_or_goal, "get", lambda _k=None: None)("correlation_id") if isinstance(task_data_or_goal, dict) else None,
                },
                execution_id=str((task_data_or_goal or {}).get("task_id") if isinstance(task_data_or_goal, dict) else ""),
            )
            if graph_result.get("status") == "success":
                return graph_result.get("output", {})
            return {
                "status": "error",
                "error": graph_result.get("error", "langgraph_failed"),
                "trace": graph_result.get("trace", []),
            }
        return await self._execute_core(task_data_or_goal, context)

    async def _execute_core(self, task_data_or_goal, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute a RAG enrichment task with fast-fail gating.
        
        Optimization: Pre-validate payload before invoking Deep Agent.
        If completeness < 0.3, return error immediately without LLM calls.
        
        Args:
            task_data_or_goal: User's goal/request (string) or task data dict
            context: Optional context (lead_data, company_data, etc.)
        
        Returns:
            Minimal result payload with enriched data
        """
        start_time = datetime.now()
        execution_id = f"exec_{start_time.timestamp()}"
        request_task_id: Optional[str] = None
        
        # Fast deterministic operations (no LLM): support orchestrator-style operation payloads.
        # This is critical for reply flows where downstream agents (Copywriter) need the full
        # lead + conversation + messages context, not just a minimal diagnostic summary.
        if isinstance(task_data_or_goal, dict):
            operation = task_data_or_goal.get("operation")
            if operation == "get_lead_context":
                request_task_id = (
                    task_data_or_goal.get("task_id")
                    or task_data_or_goal.get("correlation_id")
                    or None
                )
                email = task_data_or_goal.get("email")
                lead_id = task_data_or_goal.get("lead_id")
                conversation_limit = int(task_data_or_goal.get("conversation_limit") or 5)
                message_limit = int(task_data_or_goal.get("message_limit") or 50)

                if not self.supabase:
                    return {
                        "status": "error",
                        "task_id": request_task_id or f"exec_{start_time.timestamp()}",
                        "error": "supabase adapter unavailable",
                    }

                try:
                    from .query_strategy import cascading_lead_lookup

                    ctx_result = cascading_lead_lookup(
                        adapter=self.supabase,
                        email=email,
                        lead_id=lead_id,
                        conversation_limit=conversation_limit,
                        message_limit=message_limit,
                    )

                    # Ensure task_id is present so downstream correlators and serializers can match.
                    if isinstance(ctx_result, dict):
                        ctx_result = dict(ctx_result)
                        ctx_result["task_id"] = request_task_id or f"exec_{start_time.timestamp()}"
                    return ctx_result if isinstance(ctx_result, dict) else {
                        "status": "error",
                        "task_id": request_task_id or f"exec_{start_time.timestamp()}",
                        "error": "unexpected_context_result",
                    }
                except Exception as e:
                    logger.error(f"get_lead_context deterministic lookup failed: {e}")
                    return {
                        "status": "error",
                        "task_id": request_task_id or f"exec_{start_time.timestamp()}",
                        "error": str(e),
                    }

            # ========== FAST-PATH: build_reply_context ==========
            # Deterministic retrieval for reply generation (no LLM).
            # Returns: lead + conversation + messages for Copywriter.
            elif operation == "build_reply_context":
                request_task_id = (
                    task_data_or_goal.get("task_id")
                    or task_data_or_goal.get("correlation_id")
                    or None
                )
                email = task_data_or_goal.get("email")
                lead_id = task_data_or_goal.get("lead_id")
                thread_id = task_data_or_goal.get("thread_id")
                subject = task_data_or_goal.get("subject")
                max_messages = int(task_data_or_goal.get("max_messages") or 50)
                include_lead_profile = task_data_or_goal.get("include_lead_profile", True)
                include_all_threads = task_data_or_goal.get("include_all_threads", True)

                if not self.supabase:
                    return {
                        "status": "error",
                        "task_id": request_task_id or f"exec_{start_time.timestamp()}",
                        "error": "supabase adapter unavailable",
                    }

                try:
                    from .strategies.reply_context import build_reply_context as _build_reply_ctx

                    ctx_result = _build_reply_ctx(
                        adapter=self.supabase,
                        email=email,
                        lead_id=lead_id,
                        thread_id=thread_id,
                        subject=subject,
                        max_messages=max_messages,
                        include_lead_profile=include_lead_profile,
                        include_all_threads=include_all_threads,
                    )

                    # Ensure task_id is present for downstream correlation.
                    if isinstance(ctx_result, dict):
                        ctx_result = dict(ctx_result)
                        ctx_result["task_id"] = request_task_id or f"exec_{start_time.timestamp()}"
                        ctx_result["execution_id"] = execution_id
                        ctx_result["duration_ms"] = (datetime.now() - start_time).total_seconds() * 1000
                    logger.info(f"build_reply_context completed: status={ctx_result.get('status')}, lead_source={ctx_result.get('lead_source')}")
                    return ctx_result if isinstance(ctx_result, dict) else {
                        "status": "error",
                        "task_id": request_task_id or f"exec_{start_time.timestamp()}",
                        "error": "unexpected_context_result",
                    }
                except Exception as e:
                    logger.error(f"build_reply_context deterministic lookup failed: {e}")
                    return {
                        "status": "error",
                        "task_id": request_task_id or f"exec_{start_time.timestamp()}",
                        "error": str(e),
                    }

        # Extract goal and record from task_data
        if isinstance(task_data_or_goal, dict):
            goal = task_data_or_goal.get("goal", "")
            context = context or task_data_or_goal.get("data", {})
            record = task_data_or_goal.get("record", context.get("record", {}))
            entity_type = task_data_or_goal.get("entity_type", "lead")
            request_task_id = (
                task_data_or_goal.get("task_id")
                or task_data_or_goal.get("correlation_id")
                or None
            )
        else:
            goal = task_data_or_goal
            record = context.get("record", {}) if context else {}
            entity_type = "lead"
        
        logger.info(f"RAGAgent executing: {goal[:50]}... (id={execution_id})")
        
        # ============ FAST-FAIL GATING ============
        # Pre-validate before invoking expensive Deep Agent
        if record and validate_entity_payload and EntityType:
            try:
                entity_enum = EntityType(entity_type.lower())
                validation = validate_entity_payload(entity_enum, record)
                completeness = validation.completeness_score

                # If the caller provides a lightweight lookup key (email/id/etc.), do NOT fast-fail.
                # In interactive/RAG-tester use, the record is often just an anchor for retrieval.
                lookup_keys = {
                    "id",
                    "lead_id",
                    "email",
                    "conversation_id",
                    "thread_id",
                    "message_id",
                }
                has_lookup_key = bool(set(record.keys()) & lookup_keys)
                
                # FAST-FAIL: Return immediately if data is hopeless
                if completeness < 0.3 and not has_lookup_key:
                    logger.warning(f"Fast-fail: completeness {completeness:.2f} < 0.3")
                    return self._minimal_error_response(
                        execution_id=execution_id,
                        request_task_id=request_task_id,
                        error="insufficient_data",
                        completeness_score=completeness,
                        missing_fields=validation.missing_required_fields,
                        duration=(datetime.now() - start_time).total_seconds()
                    )
                
                logger.info(f"Validation passed: completeness={completeness:.2f}")
            except Exception as e:
                logger.warning(f"Pre-validation failed (continuing): {e}")
        
        # ============ DEEP AGENT EXECUTION ============
        try:
            lead_context_diag: Optional[Dict[str, Any]] = None

            # Deterministic diagnostics: if caller supplies a lookup anchor (email/lead_id),
            # prefetch lead context so the minimal response can always indicate whether a
            # lead was found vs. simply returning empty enrichment.
            if (
                isinstance(record, dict)
                and entity_type.lower() == "lead"
                and self.supabase
            ):
                email = record.get("email")
                lead_id = record.get("lead_id") or record.get("id")
                if email or lead_id:
                    try:
                        from .query_strategy import cascading_lead_lookup

                        lead_context_diag = cascading_lead_lookup(
                            adapter=self.supabase,
                            email=email,
                            lead_id=lead_id,
                            conversation_limit=5,
                            message_limit=50,
                        )
                    except Exception as e:
                        logger.warning(f"Lead context prefetch failed (continuing): {e}")

            # Prepare messages for Deep Agent
            messages = [
                ("system", self._get_system_prompt()),
                ("user", f"Goal: {goal}\n\nRecord: {json.dumps(record) if record else 'None'}")
            ]
            
            # Execute through Deep Agent
            result = await self.agent.ainvoke({"messages": messages})
            
            # Extract and minimize response
            if isinstance(result, dict):
                output = result.get("output", result)
            else:
                output = result
            
            # Return minimal payload
            return self._minimal_success_response(
                execution_id=execution_id,
                request_task_id=request_task_id,
                result=output,
                lead_context_diag=lead_context_diag,
                duration=(datetime.now() - start_time).total_seconds()
            )
            
        except Exception as e:
            logger.error(f"RAG execution failed: {e}", exc_info=True)
            return self._minimal_error_response(
                execution_id=execution_id,
                request_task_id=request_task_id,
                error=str(e),
                duration=(datetime.now() - start_time).total_seconds()
            )
    
    def _minimal_success_response(
        self,
        execution_id: str,
        result: Any,
        duration: float,
        request_task_id: Optional[str] = None,
        lead_context_diag: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create minimal success response to reduce stream payload size"""
        # Extract only essential fields from result
        lead_found: Optional[bool] = None
        lead_source: Optional[str] = None
        conversation_count: Optional[int] = None
        message_count: Optional[int] = None
        query_trace: Optional[Dict[str, Any]] = None

        def _apply_context_diag(diag: Dict[str, Any]) -> None:
            nonlocal lead_found, lead_source, conversation_count, message_count, query_trace
            if not isinstance(diag, dict):
                return
            if lead_found is None:
                lead_found = bool(diag.get("lead")) if ("lead" in diag) else None
            if not lead_source:
                lead_source = diag.get("lead_source")
            if conversation_count is None:
                conv = diag.get("conversations")
                if isinstance(conv, list):
                    conversation_count = len(conv)
            if message_count is None:
                msgs = diag.get("messages")
                if isinstance(msgs, list):
                    message_count = len(msgs)
            if query_trace is None:
                qt = diag.get("query_trace")
                if isinstance(qt, dict):
                    steps = qt.get("steps")
                    if isinstance(steps, list) and len(steps) > 12:
                        qt = dict(qt)
                        qt["steps"] = steps[:12]
                    query_trace = qt

        if isinstance(result, dict):
            enriched_fields = [k for k, v in result.items() if v and k not in ("status", "error", "note")]
            sources = result.get("sources", result.get("sources_used", []))
            confidence = result.get("confidence", 0.0)

            # If the output looks like get_lead_context(), include lightweight diagnostics.
            if "lead" in result or "lead_source" in result or "query_trace" in result:
                _apply_context_diag(result)
        else:
            enriched_fields = []
            sources = []
            confidence = 0.0

        # If the Deep Agent output doesn't include context, fall back to deterministic prefetch.
        if lead_context_diag:
            _apply_context_diag(lead_context_diag)
        
        response: Dict[str, Any] = {
            "status": "completed",
            # Keep task_id aligned with the request/envelope for easier correlation.
            "task_id": request_task_id or execution_id,
            "execution_id": execution_id,
            "enriched_fields": enriched_fields[:10],  # Limit field count
            "sources": sources[:5],  # Limit sources
            "confidence": confidence,
            "duration_ms": int(duration * 1000)
        }

        if lead_found is not None:
            response["lead_found"] = lead_found
        if lead_source:
            response["lead_source"] = lead_source
        if conversation_count is not None:
            response["conversation_count"] = conversation_count
        if message_count is not None:
            response["message_count"] = message_count
        if query_trace is not None:
            response["query_trace"] = query_trace

        return response
    
    def _minimal_error_response(
        self, 
        execution_id: str, 
        error: str, 
        duration: float,
        request_task_id: Optional[str] = None,
        completeness_score: float = None,
        missing_fields: List[str] = None
    ) -> Dict[str, Any]:
        """Create minimal error response"""
        response = {
            "status": "error",
            "task_id": request_task_id or execution_id,
            "execution_id": execution_id,
            "error": error[:200],  # Truncate long errors
            "duration_ms": int(duration * 1000)
        }
        if completeness_score is not None:
            response["completeness_score"] = completeness_score
        if missing_fields:
            response["missing_fields"] = missing_fields[:5]  # Limit field list
        return response
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check health of RAG Agent.
        
        Returns:
            Health status
        """
        health = {
            "status": "healthy",
            "agent": "rag",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {}
        }
        
        # Check Redis
        try:
            self.redis.ping()
            health["components"]["redis"] = "healthy"
        except Exception as e:
            health["components"]["redis"] = f"unhealthy: {e}"
            health["status"] = "degraded"
        
        # Check Deep Agent
        try:
            health["components"]["deep_agent"] = {
                "model": self.model,
                "tools_count": len(self._build_tools()),
                "status": "healthy"
            }
        except Exception as e:
            health["components"]["deep_agent"] = f"unhealthy: {e}"
            health["status"] = "degraded"
        
        return health
