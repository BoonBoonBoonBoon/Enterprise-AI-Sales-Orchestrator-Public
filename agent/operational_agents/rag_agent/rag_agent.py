from typing import Any, Optional
import re
import json
from datetime import datetime, timezone
import hashlib
import os
import time
from collections import deque
import warnings

# Prefer not to import heavy LLM/agent stacks during tests. We keep this module
# self‑contained and avoid network calls and API keys by default.
from agent.tools.persistence.service import ReadOnlyPersistenceFacade

# Provide a minimal OpenAI symbol so tests can patch it without importing heavy deps
class OpenAI:  # pragma: no cover - placeholder for tests to patch
    def __init__(self, *args, **kwargs) -> None:
        pass
    def invoke(self, prompt: str):
        return ""


# Environment / feature flag defaults (safe, local‑only)
DEFAULT_PAGE_LIMIT = int(os.environ.get("RAG_DEFAULT_LIMIT", "50"))
MAX_PAGE_LIMIT = int(os.environ.get("RAG_MAX_LIMIT", "500"))
SUMMARY_THRESHOLD = int(os.environ.get("RAG_SUMMARY_THRESHOLD", "200"))
MAX_FALLBACKS_PER_MIN = int(os.environ.get("RAG_MAX_FALLBACKS_PER_MIN", "30"))
REFORMULATION_MAX_ATTEMPTS = int(os.environ.get("RAG_REFORMULATION_MAX_ATTEMPTS", "3"))
ENABLE_CACHE = os.environ.get("RAG_CACHE_DISABLED", "0").lower() not in ("1", "true", "yes")


class _CoordinatorStub:
    """Minimal coordinator surface used by some tests.

    Tests may override `.tool` with a mock; we intentionally do nothing here.
    """

    def tool(self, *args, **kwargs):  # pragma: no cover - placeholder
        return {"status": "NOOP"}


class RAGAgent:
    """Retrieval Augmented Generation Agent (lean test‑friendly version).

    - No LLM is created at import or init time.
    - Works without any API keys present.
    - If a ReadOnlyPersistenceFacade is provided, query_* tools will use it.
    - Provides a `.coordinator` attribute with a minimal `.tool()` method so
      tests can safely patch it.
    """

    def __init__(self, read_only_persistence: Optional[ReadOnlyPersistenceFacade] = None):
        self._persistence = read_only_persistence
        # coordinator stub to satisfy tests that patch `coordinator.tool`
        self.coordinator = _CoordinatorStub()
        # No heavy agent/LLM wiring by default
        self.llm = None
        self.agent = None

        # internal state for caching and mild rate limiting
        self._query_cache: dict[str, list[dict]] = {}
        self._fallback_timestamps: deque[float] = deque()

        # Minimal tool representation to avoid importing LangChain's Tool
        class ToolLite:
            def __init__(self, name: str, func):
                self.name = name
                self.func = func

        # Register tools expected by tests/consumers
        self.tools = [
            ToolLite('query_leads', self.query_leads_tool),
            ToolLite('query_table', self.query_table_tool),
            ToolLite('rag_agent', self.rag_tool),
            ToolLite('deliver_data', self.deliver_data_disabled),
        ]

    # ------------------ Internal utility helpers ------------------
    def _stable_filter_key(self, table: str, filters: dict | None, limit: int | None, offset: int | None, order_by: str | None, descending: bool, select: list[str] | None) -> str:
        payload = {
            "t": table,
            "f": filters or {},
            "l": limit,
            "o": offset,
            "ob": order_by,
            "d": descending,
            "s": select or None,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

    def _maybe_cache_get(self, key: str):
        if not ENABLE_CACHE:
            return None
        return self._query_cache.get(key)

    def _maybe_cache_set(self, key: str, rows: list[dict]):
        if not ENABLE_CACHE:
            return
        # shallow copy to avoid accidental mutation outside
        self._query_cache[key] = [dict(r) for r in rows]

    def _debug_io(self, label: str, data: Any):  # pragma: no cover - debug instrumentation
        """Print structured debug info when RAG_DEBUG_IO env flag enabled.

        Set RAG_DEBUG_IO=1 to see inputs and outputs for tools / run calls.
        Output is truncated to 2k chars to protect the console.
        """
        if os.environ.get("RAG_DEBUG_IO", "0").lower() not in ("1", "true", "yes"):
            return
        try:
            txt = json.dumps(data, default=str)
        except Exception:
            txt = str(data)
        if len(txt) > 2000:
            txt = txt[:2000] + "...<truncated>"
        print(f"[RAG DEBUG] {label}: {txt}")

    def _deep(self, label: str, data: Any | None = None):  # pragma: no cover - deep trace
        """Print detailed step-by-step traces when RAG_DEEP_DEBUG is enabled.

        Output is truncated to 2k chars to keep logs readable.
        """
        if os.environ.get("RAG_DEEP_DEBUG", "0").lower() not in ("1", "true", "yes"):
            return
        try:
            if data is None:
                txt = ""
            else:
                txt = json.dumps(data, default=str)
        except Exception:
            txt = str(data)
        if txt and len(txt) > 2000:
            txt = txt[:2000] + "...<truncated>"
        ts = time.strftime("%H:%M:%S")
        print(f"[RAG TRACE {ts}] {label}{(': ' + txt) if txt else ''}")

    def _apply_pagination(self, rows: list[dict], limit: int | None, offset: int | None) -> list[dict]:
        if limit is None and offset is None:
            return rows
        o = max(0, offset or 0)
        if limit is None:
            return rows[o:]
        return rows[o:o + limit]

    def _summarize(self, table: str, rows: list[dict]) -> dict:
        # lightweight statistical summary (no LLM) to avoid costs
        summary = {
            "table": table,
            "sample_size": min(5, len(rows)),
            "total": len(rows),
            "fields": {},
            "strategy": "first_n_stats"
        }
        sample = rows[: summary["sample_size"]]
        # gather simple field presence / distinct counts for sample
        for r in sample:
            for k, v in r.items():
                if isinstance(v, (str, int)):
                    fld = summary["fields"].setdefault(k, {"distinct_sample": set(), "non_null": 0})
                    if v is not None:
                        fld["non_null"] += 1
                        if len(fld["distinct_sample"]) < 10:
                            fld["distinct_sample"].add(v if not isinstance(v, str) else v[:64])
        # serialize sets
        for k, meta in summary["fields"].items():
            meta["distinct_sample"] = list(meta["distinct_sample"])
        return summary

    def _rate_limit_fallback_allowed(self) -> bool:
        # purge timestamps older than 60 seconds
        now = time.time()
        while self._fallback_timestamps and now - self._fallback_timestamps[0] > 60:
            self._fallback_timestamps.popleft()
        if MAX_FALLBACKS_PER_MIN <= 0:
            return False
        if len(self._fallback_timestamps) >= MAX_FALLBACKS_PER_MIN:
            return False
        self._fallback_timestamps.append(now)
        return True

    def _reformulation_attempts(self, original_filters: dict) -> list[dict]:
        """Generate a list of relaxed filter variants (does not include original)."""
        attempts = []
        # Attempt 1: drop email if both email & company present
        if original_filters.get("email") and original_filters.get("company"):
            f = dict(original_filters)
            f.pop("email", None)
            attempts.append({"reason": "drop_email_to_broaden", "filters": f})
        # Attempt 2: shorten company (remove trailing Inc/LLC)
        comp = original_filters.get("company")
        if comp and isinstance(comp, str):
            short = re.sub(r"\b(inc|llc|corp|co)\.?$", "", comp, flags=re.IGNORECASE).strip()
            if short and short != comp:
                f = dict(original_filters)
                f["company"] = short
                attempts.append({"reason": "shorten_company_suffix", "filters": f})
        # Attempt 3: drop company entirely if still empty results
        if original_filters.get("company"):
            f = dict(original_filters)
            f.pop("company", None)
            attempts.append({"reason": "drop_company_to_broaden", "filters": f})
        return attempts[:REFORMULATION_MAX_ATTEMPTS]

    # Tool dedicated to querying the `leads` table. Only supports id, email, company filters.
    def query_leads_tool(self, args: dict):
            """Args expected: {filters: {id?: val, email?: val, company?: val}, select?: str}

            - id uses exact match
            - email uses exact match unless the value contains '%' -> ilike
            - company uses ilike with surrounding %% if a plain string is provided
            """
            # LangChain sometimes passes the tool input as a string (e.g. "{'name': 'John'}").
            # Be tolerant: if args is a string, try to parse JSON-ish input, then fall back
            # to an empty dict.
            if isinstance(args, str):
                try:
                    # try strict JSON first
                    parsed = json.loads(args)
                except Exception:
                    try:
                        # attempt a safe literal eval for Python-like dict strings
                        import ast

                        parsed = ast.literal_eval(args)
                    except Exception:
                        parsed = {}
                args = parsed if isinstance(parsed, dict) else {}

            # Accept either {'filters': {...}} or a top-level dict of filter keys
            if isinstance(args, dict) and 'filters' in args and isinstance(args.get('filters'), dict):
                raw_filters = args.get('filters') or {}
            elif isinstance(args, dict):
                # treat top-level keys (except 'select') as filters
                raw_filters = {k: v for k, v in args.items() if k != 'select'}
            else:
                raw_filters = {}

            # Colorized debug for input filters (cyan label, yellow JSON)
            if os.environ.get("RAG_DEBUG_IO", "0").lower() in ("1", "true", "yes"):  # pragma: no cover
                try:
                    import json as _json
                    print("\x1b[36m[RAG DEBUG] query_leads.input_filters:\x1b[0m \x1b[33m" + _json.dumps(raw_filters, default=str) + "\x1b[0m")
                except Exception:
                    print(f"[RAG DEBUG] query_leads.input_filters: {raw_filters}")
            # Extract pagination/sorting args before tracing to avoid UnboundLocalError
            select = args.get('select', '*')
            limit = args.get('limit')
            offset = args.get('offset')
            order_by = args.get('order_by')
            descending = bool(args.get('desc') or args.get('descending'))
            self._deep("tool.query_leads.args", {"raw": raw_filters, "select": select, "limit": limit, "offset": offset, "order_by": order_by, "descending": descending})
            # sanitize pagination
            try:
                limit = int(limit) if limit is not None else None
            except Exception:
                limit = None
            try:
                offset = int(offset) if offset is not None else None
            except Exception:
                offset = None
            if limit is not None:
                if limit <= 0:
                    limit = None
                else:
                    limit = min(limit, MAX_PAGE_LIMIT)
            filters = {}
            # id exact
            if 'id' in raw_filters and raw_filters['id'] is not None:
                filters['id'] = {'eq': raw_filters['id']}
            # email: allow ilike if wildcard present
            if 'email' in raw_filters and raw_filters['email'] is not None:
                v = raw_filters['email']
                if isinstance(v, str) and ('%' in v or '*' in v):
                    v = v.replace('*', '%')
                    filters['email'] = {'ilike': v}
                else:
                    filters['email'] = {'eq': v}
            # company: use ilike partial match if supported; otherwise fallback to equality
            if 'company' in raw_filters and raw_filters['company'] is not None:
                v = raw_filters['company']
                cap = {}
                if self._persistence is not None and hasattr(self._persistence, 'capabilities'):
                    try:
                        cap = self._persistence.capabilities() or {}
                    except Exception:
                        cap = {}
                supports_ilike = bool(cap.get('ilike'))
                if isinstance(v, str) and ('%' in v or '*' in v):
                    cleaned = v.replace('*', '%')
                    if supports_ilike:
                        filters['company_name'] = {'ilike': cleaned}
                    else:
                        # remove % for equality fallback
                        filters['company_name'] = {'eq': cleaned.strip('%')}
                else:
                    if supports_ilike:
                        filters['company_name'] = {'ilike': f"%{v}%"}
                    else:
                        filters['company_name'] = {'eq': v}

            # client_id exact match
            if 'client_id' in raw_filters and raw_filters['client_id'] is not None:
                filters['client_id'] = {'eq': raw_filters['client_id']}

            # 'name' filter removed: ignore it to avoid unstable behavior.
            # Use the deterministic DataCoordinator to fetch structured envelopes
            # The coordinator will whitelist filters and return a dict envelope
            # Delegate to the DataCoordinator.tool wrapper which will whitelist keys
            # If we have a persistence facade: perform query directly
            if self._persistence is not None:
                # Convert our filter schema (eq / ilike shapes) to flat equality for now; facade currently expects {col: value}
                flat_filters = {}
                for k, cond in filters.items():
                    if isinstance(cond, dict):
                        if 'eq' in cond:
                            flat_filters[k] = cond['eq']
                        elif 'ilike' in cond:
                            # if capability not present, strip wildcards
                            cap = {}
                            if self._persistence is not None and hasattr(self._persistence, 'capabilities'):
                                try:
                                    cap = self._persistence.capabilities() or {}
                                except Exception:
                                    cap = {}
                            if cap.get('ilike'):
                                flat_filters[k] = cond['ilike']
                            else:
                                flat_filters[k] = cond['ilike'].strip('%')
                    else:
                        flat_filters[k] = cond
                # Determine backend name for observability (supabase vs memory)
                try:
                    adapter = getattr(getattr(self._persistence, "_svc", None), "adapter", None)
                    backend_name = type(adapter).__name__.replace('Adapter','').lower() if adapter else 'persistence'
                except Exception:
                    backend_name = 'persistence'
                # Build cache key
                cache_key = self._stable_filter_key('leads', flat_filters or None, limit, offset, order_by, descending, None)
                cached = self._maybe_cache_get(cache_key)
                if cached is not None:
                    rows = cached
                    cache_hit = True
                else:
                    rows_full = self._persistence.query('leads', filters=flat_filters or None, limit=None, order_by=order_by, descending=descending, select=None)
                    # apply manual offset/limit (adapter interface has no offset)
                    rows = self._apply_pagination(rows_full, limit or DEFAULT_PAGE_LIMIT if limit is None else limit, offset)
                    self._maybe_cache_set(cache_key, rows)
                    cache_hit = False
                self._deep("tool.query_leads.persistent_query", {"filters": flat_filters or None, "order_by": order_by, "descending": descending, "limit": limit, "offset": offset, "cache": "hit" if cache_hit else "miss", "row_count": len(rows)})
                now = datetime.now(timezone.utc).isoformat()
                envelope = {
                    'metadata': {
                        'source': f'{backend_name}.leads',
                        'backend': backend_name,
                        'retrieved_at': now,
                        'query_filters': flat_filters or None,
                        'total_count': len(rows),
                        'cache': 'hit' if cache_hit else 'miss',
                        'limit': limit or DEFAULT_PAGE_LIMIT if limit is not None else None,
                        'offset': offset or 0,
                    },
                    'records': rows,
                }
                if os.environ.get("RAG_DEBUG_IO", "0").lower() in ("1", "true", "yes"):  # pragma: no cover
                    try:
                        import json as _json
                        print("\x1b[36m[RAG DEBUG] query_leads.output_envelope:\x1b[0m \x1b[32m" + _json.dumps(envelope, default=str)[:2000] + "\x1b[0m")
                    except Exception:
                        pass
                self._deep("tool.query_leads.envelope", envelope)
                return envelope
            # No persistence facade: return error envelope
            fallback_env = {'metadata': {'source': 'leads', 'error': 'no data backend available'}, 'records': []}
            if os.environ.get("RAG_DEBUG_IO", "0").lower() in ("1", "true", "yes"):  # pragma: no cover
                try:
                    import json as _json
                    print("\x1b[36m[RAG DEBUG] query_leads.output_envelope:\x1b[0m \x1b[32m" + _json.dumps(fallback_env, default=str)[:2000] + "\x1b[0m")
                except Exception:
                    pass
            return fallback_env

    def rag_tool(self, args: Any):
        """Tool wrapper so the RAGAgent can be called as a LangChain Tool.

        Accepts either a free-text prompt, a dict payload containing keys like
        'prompt'/'text'/'query', or a canonical envelope that already contains
        'records'. If an envelope with 'records' is provided, this method
        returns it immediately (after adding minimal metadata if missing).
        Otherwise it coerces a prompt and calls `self.run(..., return_json=True)`.
        """

        # Fast-path: if caller already provided records/envelope, return it directly
        payload = args
        if isinstance(args, str):
            try:
                parsed = json.loads(args)
            except Exception:
                try:
                    import ast

                    parsed = ast.literal_eval(args)
                except Exception:
                    parsed = None
            if isinstance(parsed, dict):
                payload = parsed

        if isinstance(payload, dict) and 'records' in payload and isinstance(payload['records'], list):
            # ensure minimal metadata
            if 'metadata' not in payload or not isinstance(payload.get('metadata'), dict):
                now = datetime.now(timezone.utc).isoformat()
                payload = {
                    'metadata': {
                        'source': 'rag_agent',
                        'query_filters': payload.get('query_filters') if isinstance(payload.get('query_filters'), dict) else None,
                        'retrieved_at': now,
                        'total_count': len(payload['records'])
                    },
                    'records': payload['records']
                }
            return payload

        # coerce a prompt from args
        prompt = None
        if isinstance(args, str):
            prompt = args
        elif isinstance(args, dict):
            prompt = args.get('prompt') or args.get('text') or args.get('query')
        else:
            try:
                s = args.decode('utf-8') if isinstance(args, (bytes, bytearray)) else str(args)
                try:
                    parsed = json.loads(s)
                except Exception:
                    try:
                        import ast

                        parsed = ast.literal_eval(s)
                    except Exception:
                        parsed = None
                if isinstance(parsed, dict):
                    prompt = parsed.get('prompt') or parsed.get('text') or parsed.get('query')
                else:
                    prompt = s
            except Exception:
                prompt = str(args)

        if not prompt:
            now = datetime.now(timezone.utc).isoformat()
            return {
                'metadata': {
                    'source': 'rag_agent',
                    'query_filters': None,
                    'retrieved_at': now,
                    'total_count': 0,
                    'error': 'missing prompt'
                },
                'records': [],
            }

        try:
            envelope = self.run(prompt, return_json=True)
            return envelope
        except Exception as e:
            now = datetime.now(timezone.utc).isoformat()
            return {
                'metadata': {
                    'source': 'rag_agent',
                    'query_filters': None,
                    'retrieved_at': now,
                    'total_count': 0,
                    'error': str(e)
                },
                'records': [],
            }

    # helpers to call the llm/agent using newer 'invoke' APIs when available
    def _llm_call(self, prompt: str):
        """Placeholder LLM call that avoids network access in tests.

        Returns an empty string by default. If a real LLM is injected onto
        `self.llm` with an `invoke` method, we'll use it.
        """
        if self.llm is None:
            return ""
        try:
            if hasattr(self.llm, "invoke"):
                resp = self.llm.invoke(prompt)
                if isinstance(resp, dict):
                    return resp.get("output") or resp.get("text") or json.dumps(resp)
                if hasattr(resp, "text"):
                    return getattr(resp, "text")
                if hasattr(resp, "content"):
                    return getattr(resp, "content")
                return str(resp)
        except Exception:
            return ""
        return ""

    def _agent_call(self, prompt: str):
        """Invoke the LangChain agent robustly without leaking exceptions.

        LangChain agent interfaces have evolved (invoke/run/call) and tool
        planning can raise validation errors when an expected structured
        argument (e.g. {"table": "leads"}) is missing. We attempt a series
        of invocation patterns and swallow/record errors, returning a
        best‑effort string so higher layers (envelope builders) can proceed.
        """

        errors: list[str] = []

        def _norm(resp: Any):  # local normalizer
            if isinstance(resp, dict):
                return resp.get('output') or resp.get('text') or json.dumps(resp)
            if hasattr(resp, 'output'):
                return getattr(resp, 'output')
            if hasattr(resp, 'text'):
                return getattr(resp, 'text')
            return str(resp)

        self._deep("agent.call.start", {"prompt": prompt})
        if self.agent is None:
            return "agent_noop"
        # 1. agent.invoke with raw prompt
        if hasattr(self.agent, 'invoke'):
            try:
                self._deep("agent.invoke(str).attempt")
                return _norm(self.agent.invoke(prompt))
            except Exception as e:  # capture and continue
                errors.append(f"invoke(str) -> {e.__class__.__name__}: {e}")
                self._deep("agent.invoke(str).error", str(e))
        # 2. agent.run with raw prompt
        if hasattr(self.agent, 'run'):
            try:
                self._deep("agent.run(str).attempt")
                return _norm(self.agent.run(prompt))
            except Exception as e:
                errors.append(f"run(str) -> {e.__class__.__name__}: {e}")
                self._deep("agent.run(str).error", str(e))
        # 3. agent.invoke with dict {input: prompt}
        if hasattr(self.agent, 'invoke'):
            try:
                self._deep("agent.invoke(dict).attempt", {"input": prompt})
                return _norm(self.agent.invoke({'input': prompt}))
            except Exception as e:
                errors.append(f"invoke(dict-input) -> {e.__class__.__name__}: {e}")
                self._deep("agent.invoke(dict).error", str(e))
        # 4. Direct __call__ if defined
        try:
            self._deep("agent.__call__.attempt")
            return _norm(self.agent(prompt))  # type: ignore[call-arg]
        except Exception as e:
            errors.append(f"__call__ -> {e.__class__.__name__}: {e}")
            self._deep("agent.__call__.error", str(e))

        # 5. As a last resort return a compact diagnostic string (do NOT raise)
        if errors:
            diag = "agent_fallback_error:" + " | ".join(errors[:3])
            self._deep("agent.call.end", {"errors": errors, "diag": diag})
            return diag  # truncate to first few for brevity
        self._deep("agent.call.end", {"status": "no_response"})
        return "agent_no_response"

    def _normalize_filters(self, filters: dict) -> dict:
        """Return a copy of filters mapped to DB column names and normalized shapes."""
        if not filters or not isinstance(filters, dict):
            return {}
        q = dict(filters)
        # map company -> company_name
        if 'company' in q:
            q['company_name'] = q.pop('company')
        # client_id passthrough (already fine)
        # drop 'name' filters entirely to avoid unstable name-based searches
        if 'name' in q:
            q.pop('name', None)
        return q

    def run(self, prompt: str, return_json: bool = False, include_raw: bool = False, fallback_on_empty: bool = True, limit: int | None = None, offset: int | None = None):
        """Run the agent with a given prompt.

        Fast path:
            * Extract structured filters (rule-based or LLM-assisted) and query directly.
        Fallback path:
            * If no filters OR (filters produced zero rows and fallback_on_empty=True) → invoke LangChain agent
              to attempt reasoning/tool selection (emits thinking output when verbose).

        Args:
            prompt: Free-text user input.
            return_json: If True, returns a canonical envelope.
            include_raw: If True, provenance embeds raw row copy.
            fallback_on_empty: If True (default) and the fast-path query returns 0 rows, perform an
                agent reasoning fallback. The envelope will include metadata.fallback = 'agent'.
        """
        # Try to extract structured filters from the prompt first. If we can,
        # execute the leads query directly. Otherwise defer to the LangChain agent
        # which may plan and call the tool itself.
        self._deep("run.start", {"prompt": prompt, "return_json": return_json, "include_raw": include_raw, "fallback_on_empty": fallback_on_empty, "limit": limit, "offset": offset})
        try:
            filters = self.parse_filters_from_text(prompt)
        except Exception:
            filters = {}
        self._deep("parse.rule", filters)

        # We intentionally avoid LLM-assisted parsing in this lean version to
        # keep tests offline and deterministic.

        if filters:
            # call the leads tool directly for predictable behavior
            tool = next(t for t in self.tools if t.name == 'query_leads')
            q_filters = self._normalize_filters(filters)
            self._deep("filters.normalized", q_filters)
            # If caller wants machine-readable output, return an envelope with provenance
            if return_json:
                # Always use normalized deterministic filters (drop 'name' if present)
                # Use persistence facade when available; else legacy supabase path
                # pagination controls
                try:
                    if limit is not None:
                        limit = int(limit)
                except Exception:
                    limit = None
                try:
                    if offset is not None:
                        offset = int(offset)
                except Exception:
                    offset = None
                if limit is not None:
                    if limit <= 0:
                        limit = None
                    else:
                        limit = min(limit, MAX_PAGE_LIMIT)

                # Determine backend name for observability
                try:
                    adapter = getattr(getattr(self._persistence, "_svc", None), "adapter", None)
                    backend_name = type(adapter).__name__.replace('Adapter','').lower() if adapter else 'persistence'
                except Exception:
                    backend_name = 'persistence'
                all_rows = self._persistence.query('leads', filters=q_filters or None, limit=None)
                self._deep("persistence.query", {"table": "leads", "filters": q_filters or None, "rows_all": len(all_rows) if isinstance(all_rows, list) else None})
                records = self._apply_pagination(all_rows, limit or DEFAULT_PAGE_LIMIT if limit is None else limit, offset)
                self._deep("pagination.apply", {"limit": limit, "offset": offset, "rows_out": len(records)})

                now = datetime.now(timezone.utc).isoformat()
                envelope = {
                    "metadata": {
                        "source": f"{backend_name}.leads",
                        "backend": backend_name,
                        "query_filters": q_filters,
                        "retrieved_at": now,
                        "total_count": len(records)
                    },
                    "records": []
                }
                for r in records:
                    rec = dict(r)
                    # minimal provenance by default to avoid duplicating tokens
                    prov = {
                        "source": "supabase.leads",
                        "row_id": r.get('id'),
                        "row_hash": hashlib.sha256(repr(sorted(r.items())).encode('utf-8')).hexdigest(),
                        "retrieved_at": now
                    }
                    if include_raw:
                        # include the full raw row only when explicitly requested
                        prov['raw_row'] = dict(r)
                    rec['provenance'] = prov
                    envelope['records'].append(rec)
                # Large result handling summary
                if envelope['metadata']['total_count'] > SUMMARY_THRESHOLD:
                    envelope['metadata']['truncated'] = True
                    envelope['metadata']['summary'] = self._summarize('leads', envelope['records'])
                # Fallback / Reformulation logic
                if envelope['metadata']['total_count'] == 0 and fallback_on_empty:
                    # 1) Attempt reformulations
                    reform_attempts_meta = []
                    attempts = self._reformulation_attempts(q_filters)
                    self._deep("fallback.reformulation.attempts", attempts)
                    for attempt in attempts:
                        f2 = attempt['filters']
                        rows2_all = self._persistence.query('leads', filters=f2)
                        rows2 = self._apply_pagination(rows2_all, limit or DEFAULT_PAGE_LIMIT if limit is None else limit, offset)
                        reform_attempts_meta.append({"reason": attempt['reason'], "filters": f2, "result_count": len(rows2)})
                        self._deep("fallback.reformulation.result", {"reason": attempt['reason'], "filters": f2, "count": len(rows2)})
                        if rows2:
                            envelope['records'] = []
                            for r in rows2:
                                rec = dict(r)
                                prov = {
                                    "source": "supabase.leads",
                                    "row_id": r.get('id'),
                                    "row_hash": hashlib.sha256(repr(sorted(r.items())).encode('utf-8')).hexdigest(),
                                    "retrieved_at": now,
                                }
                                if include_raw:
                                    prov['raw_row'] = dict(r)
                                rec['provenance'] = prov
                                envelope['records'].append(rec)
                            envelope['metadata']['total_count'] = len(rows2)
                            envelope['metadata']['fallback'] = 'reformulation'
                            envelope['metadata']['reformulation_attempts'] = reform_attempts_meta
                            break
                    # 2) Agent fallback if still empty and rate limit allows
                    if envelope['metadata']['total_count'] == 0:
                        if self._rate_limit_fallback_allowed():
                            self._deep("fallback.agent.begin")
                            agent_response = self._agent_call(prompt)
                            envelope['metadata']['fallback'] = 'agent'
                            envelope['records'].append({
                                'response': agent_response,
                                'provenance': {
                                    'source': 'agent',
                                    'retrieved_at': now
                                }
                            })
                            self._deep("fallback.agent.end", {"response_preview": str(agent_response)[:200]})
                        else:
                            envelope['metadata']['fallback'] = 'suppressed'
                        envelope['metadata']['reformulation_attempts'] = reform_attempts_meta
                self._deep("run.end.envelope", {"metadata": envelope['metadata'], "records_len": len(envelope['records'])})
                return envelope
            else:
                result = tool.func({'filters': filters, 'select': '*'})
                # result is an envelope-like dict already
                if fallback_on_empty and isinstance(result, dict) and result.get('metadata', {}).get('total_count') == 0:
                    agent_response = self._agent_call(prompt)
                    # augment result with fallback info
                    result.setdefault('metadata', {})['fallback'] = 'agent'
                    result.setdefault('records', []).append({'response': agent_response})
                if os.environ.get('RAG_DEBUG'):
                    print('[RAG_DEBUG] fast-path result', json.dumps({
                        'metadata': result.get('metadata'),
                        'records_len': len(result.get('records', []))
                    }, default=str), flush=True)
                return result

        # Optional deterministic default when no filters are present (small list) before pure agent
        if os.environ.get('RAG_DEFAULT_LIST_ON_EMPTY', '1') in ('1','true','TRUE') and return_json:
            self._deep('default_list.on_empty.begin')
            now = datetime.now(timezone.utc).isoformat()
            try:
                rows = self._persistence.query('leads', filters=None, limit=DEFAULT_PAGE_LIMIT)
                source = 'persistence.leads'
                records = self._apply_pagination(rows, DEFAULT_PAGE_LIMIT, None)
                env = {
                    'metadata': {
                        'source': source,
                        'query_filters': None,
                        'retrieved_at': now,
                        'total_count': len(records),
                        'note': 'default_list_on_empty'
                    },
                    'records': records,
                }
                self._deep('default_list.on_empty.envelope', {"count": len(records)})
                if env['metadata']['total_count'] == 0 and fallback_on_empty:
                    self._deep('default_list.on_empty.empty_fallback')
                    agent_response = self._agent_call(prompt)
                    env['metadata']['fallback'] = 'agent'
                    env['records'].append({'response': agent_response, 'provenance': {'source': 'agent', 'retrieved_at': now}})
                return env
            except Exception:
                # If default list fails, proceed to pure agent
                pass

        # fallback to agent reasoning which can use the tool if needed
        self._deep("pure_agent.begin")
        agent_response = self._agent_call(prompt)
        if return_json:
            # Wrap fallback agent response in a JSON envelope
            now = datetime.now(timezone.utc).isoformat()
            env = {
                "metadata": {
                    "source": "agent",
                    "query_filters": None,
                    "retrieved_at": now,
                    "total_count": 1
                },
                "records": [
                    {
                        "response": agent_response,
                        "provenance": {
                            "source": "agent",
                            "retrieved_at": now
                        }
                    }
                ]
            }
            if os.environ.get('RAG_DEBUG'):
                print('[RAG_DEBUG] pure-agent envelope', json.dumps(env, default=str), flush=True)
            self._deep("pure_agent.end.envelope", env)
            return env
        return agent_response

    def parse_filters_with_llm(self, text: str) -> dict:
        """Use the agent's LLM to extract id/email/company as strict JSON.

        The LLM is asked to return only JSON with keys id, email, company (use null for missing).
        The method validates and sanitizes the output before returning it.
        """
        if not text or not isinstance(text, str):
            return {}
        # Without a real LLM, there is nothing to parse; keep conservative.
        return {}

    def parse_filters_from_text(self, text: str) -> dict:
        """Simple rule-based NL parser to extract id, email, company from text.

        Returns a dict suitable for the `query_leads` tool: {'id': val, 'email': val, 'company': val}
        The parser looks for common phrasing and email patterns. It is intentionally
        conservative to avoid accidental broad queries.
        """
        if not text or not isinstance(text, str):
            return {}

        out = {}

        # client_id: explicit phrase (prefer this over id when present)
        m = re.search(r"client[_ ]?id\s*[:=]?\s*([0-9A-Za-z\-]{2,})\b", text, re.IGNORECASE)
        if m:
            out['client_id'] = m.group(1)

        # id: 'id 123' or 'id: 123' or 'id = 123'
        m = re.search(r"\bid\s*[:=]?\s*([0-9A-Za-z\-]{2,})\b", text, re.IGNORECASE)
        if m:
            out['id'] = m.group(1)

        # explicit email address
        m = re.search(r"([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})", text)
        if m:
            out['email'] = m.group(1)
        else:
            # patterns like 'email contains example.com' or 'email with example.com' or '@example.com'
            m = re.search(r"email\s*(?:contains|with|like|that contains)?\s*[:\"]?([^\s,;']+\.[A-Za-z]{2,})", text, re.IGNORECASE)
            if m:
                v = m.group(1)
                # turn domain-like into wildcard search
                if '@' in v or '.' in v:
                    out['email'] = f"%{v}%"
                else:
                    out['email'] = v
            else:
                m = re.search(r"@([A-Za-z0-9.\-]+\.[A-Za-z]{2,})", text)
                if m:
                    out['email'] = f"%{m.group(1)}%"

        # company: try phrases 'company X', 'from X', 'at X', 'works at X', 'of X'
        m = re.search(r"(?:company|from|at|works at|of)\s+[\"']?([A-Z0-9][\w&.\- ]{1,60})[\"']?", text, re.IGNORECASE)
        if m:
            comp = m.group(1).strip()
            out['company'] = comp

        # Normalize wildcard markers '*' -> '%' for email/company if present
        for k in ['email', 'company']:
            if k in out and isinstance(out[k], str):
                out[k] = out[k].replace('*', '%')

        return out

    def query_leads(self, id: str = None, email: str = None, company: str = None, select: str = '*'):
        """Convenience method to query the `leads` table directly from Python.

        Supports filtering by id (exact), email (exact or wildcard '%'), and company (partial match).
        Returns a human-readable summary string of matching records.
        """
        warnings.warn(
            "RAGAgent.query_leads is deprecated; prefer using query_leads_tool via tools or the JSON envelope run().",
            DeprecationWarning,
            stacklevel=2,
        )
        raw_filters = {}
        if id is not None:
            raw_filters['id'] = id
        if email is not None:
            raw_filters['email'] = email
        if company is not None:
            raw_filters['company'] = company
        # reuse the tool logic by calling the tool func directly
        tool = next(t for t in self.tools if t.name == 'query_leads')
        return tool.func({'filters': raw_filters, 'select': select})

    def deliver_data_tool(self, args: dict):
        """Deliver a JSON envelope to a named downstream agent.

        Expected args: {'envelope': {...}, 'target_agent': 'agent_name'}
        This is a placeholder; replace with your actual agent dispatch/registry logic.
        """
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                try:
                    import ast

                    args = ast.literal_eval(args)
                except Exception:
                    return {"status": "ERROR", "error": "invalid args"}

        if not isinstance(args, dict):
            return {"status": "ERROR", "error": "args must be a dict"}

        # accept several possible keys used by planners/tools
        envelope = args.get("envelope") or args.get("json_envelope") or args.get("json")
        target = args.get("target_agent") or args.get("agent_name") or args.get("target")
        if not envelope or not target:
            return {"status": "ERROR", "error": "missing envelope or target_agent"}

        # TODO: wire this into your agent registry or message bus. Placeholder below records delivery metadata.
        delivered_at = datetime.now(timezone.utc).isoformat()
        return {"status": "DELIVERED", "delivered_to": target, "delivered_at": delivered_at}

    def deliver_data_disabled(self, args: dict):
        """Temporary disabled delivery tool: quickly respond that delivery is disabled.

        Keep the signature compatible with the active tool so planners won't crash,
        but avoid any external side-effects until we wire a real dispatch path.
        """
        return {"status": "DISABLED", "reason": "delivery temporarily disabled"}

    def query_table_tool(self, args: dict):
        """Generic query tool for any allowed read table via persistence facade.

        Args shape examples:
        {"table": "clients", "filters": {"name": "Acme"}}
        {"table": "campaigns"}  # no filters

        Returns JSON envelope with metadata + records, or error metadata on failure.
        """
        if self._persistence is None:
            return {"metadata": {"source": "persistence", "error": "persistence facade not injected"}, "records": []}
        # tolerant parsing for string input
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                try:
                    import ast
                    args = ast.literal_eval(args)
                except Exception:
                    return {"metadata": {"source": "persistence", "error": "invalid args"}, "records": []}
        if not isinstance(args, dict):
            return {"metadata": {"source": "persistence", "error": "args must be dict"}, "records": []}
        table = (args.get('table') or '').strip().lower()
        filters = args.get('filters') if isinstance(args.get('filters'), dict) else None
        now = datetime.now(timezone.utc).isoformat()
        if not table:
            return {"metadata": {"source": "persistence", "error": "missing table", "retrieved_at": now}, "records": []}
        try:
            rows = self._persistence.query(table, filters=filters or None)
            return {
                'metadata': {
                    'source': f'persistence.{table}',
                    'retrieved_at': now,
                    'query_filters': filters or None,
                    'total_count': len(rows),
                },
                'records': rows,
            }
        except Exception as e:  # surface failure as envelope metadata
            return {
                'metadata': {
                    'source': f'persistence.{table}',
                    'retrieved_at': now,
                    'query_filters': filters or None,
                    'total_count': 0,
                    'error': str(e),
                },
                'records': [],
            }


# predictable symbol for runtime discovery
AGENT_CLASS = RAGAgent
