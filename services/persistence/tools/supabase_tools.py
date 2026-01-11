"""Supabase tools (migrated from agent.tools.supabase_tools).

This module is still considered legacy; new code should prefer using
`PersistenceService` + Supabase adapters via the persistence layer.
"""

from supabase import create_client
from config.settings import SUPABASE_URL, SUPABASE_KEY
import warnings
from typing import Any, Dict, List, Optional


warnings.warn(
	"services.persistence.tools.supabase_tools is legacy and will be removed in a future release. "
	"Use PersistenceService + SupabaseAdapter instead.",
	DeprecationWarning,
	stacklevel=2,
)


class SupabaseClient:
	"""Light wrapper around the Supabase python client to query arbitrary tables."""

	def __init__(self) -> None:
		if not SUPABASE_URL or not SUPABASE_KEY:
			raise EnvironmentError("SUPABASE_URL and SUPABASE_KEY must be set in env")
		self.client = create_client(SUPABASE_URL, SUPABASE_KEY)

	def _apply_filters(self, query_builder, filters: Optional[Dict[str, Any]]):
		if not filters:
			return query_builder
		for col, cond in filters.items():
			if isinstance(cond, dict):
				for op, val in cond.items():
					op = op.lower()
					method = getattr(query_builder, op, None)
					if callable(method):
						try:
							query_builder = method(col, val)
						except TypeError:
							query_builder = method(col, val)
					else:
						try:
							query_builder = query_builder.filter(col, op, val)
						except Exception:
							query_builder = query_builder.eq(col, val)
			else:
				query_builder = query_builder.eq(col, cond)
		return query_builder

	def query_table(self, table: str, filters: Optional[Dict[str, Any]] = None, select: str = "*") -> List[Dict[str, Any]]:
		qb = self.client.table(table).select(select)
		qb = self._apply_filters(qb, filters)
		result = qb.execute()
		data = None
		error = None
		if hasattr(result, "data"):
			data = result.data
		if hasattr(result, "error"):
			error = result.error
		if data is None and isinstance(result, dict):
			data = result.get("data")
			error = error or result.get("error")
		if error:
			msg = error.message if hasattr(error, "message") else str(error)
			raise RuntimeError(f"Supabase query error: {msg}")
		return data or []


def format_records(records: List[Dict[str, Any]], limit: int = 20) -> str:
	"""Return a short human-readable summary for a list of dict records."""
	if not records:
		return "(no records)"
	out_lines: list[str] = []
	for i, r in enumerate(records[:limit], 1):
		items = ", ".join(f"{k}={v}" for k, v in r.items())
		out_lines.append(f"{i}. {items}")
	if len(records) > limit:
		out_lines.append(f"...and {len(records)-limit} more records")
	return "\n".join(out_lines)


TOOL = SupabaseClient
