"""Deterministic Data Coordinator (LEGACY / DEPRECATED)

DEPRECATION STATUS:
-------------------
Kept temporarily only to support the RAGAgent legacy fallback mode when
no `ReadOnlyPersistenceFacade` is supplied. Once all call sites migrate
to constructing RAGAgent via the factory (`create_rag_agent`) this module
will be removed.

Modern Replacement:
- Use `ReadOnlyPersistenceFacade.query()` directly, optionally wrapping
    higher-level retrieval logic in a dedicated context builder.

Do not extend this module. It intentionally remains minimal.
"""
from typing import Any, Dict, List, Optional
import json
import ast
import hashlib
from datetime import datetime, timezone

from agent.tools.supabase_tools import SupabaseClient


class DataCoordinator:
    """Minimal deterministic coordinator for leads queries.

    This implementation is intentionally conservative: it whitelists a small
    set of filter keys and produces a stable supabase filter shape used by
    `SupabaseClient.query_table`.
    """

    ALLOWED_KEYS = {"id", "client_id", "email", "company", "company_name"}

    def __init__(self, supabase: Optional[SupabaseClient] = None):
        self.supabase = supabase

    def _normalize_filters(self, raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Normalize incoming filters to the per-column op-shape expected
        by the Supabase client.

        Examples:
        - {'company': 'Acme'} -> {'company_name': {'ilike': '%Acme%'}}
        - {'email': '%example.com%'} -> {'email': {'ilike': '%example.com%'}}
        - {'id': '123'} -> {'id': {'eq': '123'}}
        """
        if not raw or not isinstance(raw, dict):
            return {}

        out: Dict[str, Any] = {}

        for k, v in raw.items():
            if k not in self.ALLOWED_KEYS:
                # tolerate 'company' mapping below even if caller used company
                if k == 'company' and 'company_name' not in raw:
                    pass
                else:
                    continue

            if v is None:
                continue

            # map company -> company_name
            col = 'company_name' if k in ('company', 'company_name') else k

            # email wildcard detection
            if col == 'email' and isinstance(v, str):
                s = v.replace('*', '%')
                if '%' in s:
                    out[col] = {'ilike': s}
                else:
                    out[col] = {'eq': s}
                continue

            # company: do partial match
            if col == 'company_name' and isinstance(v, str):
                s = v.replace('*', '%')
                if '%' in s:
                    out[col] = {'ilike': s}
                else:
                    out[col] = {'ilike': f"%{s}%"}
                continue

            # id and client_id: exact
            if col in ('id', 'client_id'):
                out[col] = {'eq': v}
                continue

            # fallback: equality
            out[col] = {'eq': v}

        return out

    def get_leads(self, filters: Optional[Dict[str, Any]] = None, select: str = '*') -> Dict[str, Any]:
        """Run a deterministic query against `leads` and return an envelope.

        The envelope includes metadata.query_filters (the normalized filters),
        records (list of dict rows) and lightweight provenance for each row.
        """
        sb_filters = self._normalize_filters(filters or {})

        now = datetime.now(timezone.utc).isoformat()

        if not self.supabase:
            # graceful empty envelope when no supabase client is available
            return {
                "metadata": {
                    "source": "supabase.leads",
                    "query_filters": sb_filters,
                    "retrieved_at": now,
                    "total_count": 0,
                    "note": "no_supabase_client"
                },
                "records": [],
            }

        rows = []
        try:
            rows = self.supabase.query_table('leads', filters=sb_filters if sb_filters else None, select=select)
        except Exception as e:
            # return an envelope with the error encoded rather than raise to keep tool-safe
            return {
                "metadata": {
                    "source": "supabase.leads",
                    "query_filters": sb_filters,
                    "retrieved_at": now,
                    "total_count": 0,
                    "error": str(e),
                },
                "records": [],
            }

        envelope_records: List[Dict[str, Any]] = []
        for r in rows or []:
            rec = dict(r)
            row_id = rec.get('id')
            # stable row hash for provenance
            try:
                row_hash = hashlib.sha256(repr(sorted(rec.items())).encode('utf-8')).hexdigest()
            except Exception:
                row_hash = hashlib.sha256(repr(rec).encode('utf-8')).hexdigest()

            prov = {
                "source": "supabase.leads",
                "row_id": row_id,
                "row_hash": row_hash,
                "retrieved_at": now,
            }
            rec['provenance'] = prov
            envelope_records.append(rec)

        return {
            "metadata": {
                "source": "supabase.leads",
                "query_filters": sb_filters,
                "retrieved_at": now,
                "total_count": len(envelope_records),
            },
            "records": envelope_records,
        }

    def tool(self, args: Any) -> Dict[str, Any]:
        """Tool wrapper compatible with LangChain tools.

        Accepts either a dict or a JSON/string representation. Recognized input
        shapes:
        - {'filters': {...}, 'select': '...'}
        - {'id': 'x', 'email': 'y'} (top-level treated as filters)
        - JSON string of the above
        """
        if isinstance(args, str):
            parsed = {}
            try:
                parsed = json.loads(args)
            except Exception:
                try:
                    parsed = ast.literal_eval(args)
                except Exception:
                    parsed = {}
            args = parsed if isinstance(parsed, dict) else {}

        if not isinstance(args, dict):
            args = {}

        if 'filters' in args and isinstance(args.get('filters'), dict):
            raw_filters = args.get('filters') or {}
        else:
            # treat top-level keys except 'select' as filters
            raw_filters = {k: v for k, v in args.items() if k != 'select'}

        select = args.get('select', '*')

        return self.get_leads(raw_filters, select=select)

    __call__ = tool
