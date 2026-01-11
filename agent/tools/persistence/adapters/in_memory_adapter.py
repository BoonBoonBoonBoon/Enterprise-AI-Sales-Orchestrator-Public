"""In-memory persistence adapter.

Lightweight test/dummy backend implementing the PersistenceAdapter contract.
Intended strictly for tests and local experimentation; not thread-safe and not
optimized for large datasets. The goal is API parity with the subset used by
RAG flows (read/query with equality and simple wildcard matching).
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional, Set


class InMemoryAdapter:
	def __init__(self) -> None:
		self._tables: Dict[str, List[Dict[str, Any]]] = {}
		self._counters: Dict[str, int] = {}
		self.capabilities = {
			"equality_filters": True,
			"ordering": True,
			"limit": True,
			"projections": True,
			"ilike": True,  # enable case-insensitive wildcard support for tests
			"range_operators": False,
			"in_operator": False,
		}

	# Internal helpers --------------------------------------------------
	def _ensure(self, table: str) -> None:
		if table not in self._tables:
			self._tables[table] = []
			self._counters[table] = 1

	def _wildcard_match(self, value: Any, pattern: str) -> bool:
		"""Case-insensitive substring match where '%' acts as a multi-char wildcard."""
		if not isinstance(value, str):
			return False
		parts = pattern.lower().split("%")
		cursor = value.lower()
		pos = 0
		for part in parts:
			if not part:
				continue
			idx = cursor.find(part, pos)
			if idx == -1:
				return False
			pos = idx + len(part)
		return True

	def clear_tables(self) -> None:
		"""Test helper: reset all stored rows across all tables."""
		self._tables.clear()
		self._counters.clear()

	# Write ops ---------------------------------------------------------
	def write(self, table: str, record: Dict[str, Any]) -> Dict[str, Any]:
		self._ensure(table)
		# Preserve provided id if present; otherwise assign sequential id
		provided_id = record.get("id")
		if provided_id is None:
			rid = str(self._counters[table])
			self._counters[table] += 1
		else:
			rid = provided_id
		stored = {**record, "id": rid}
		self._tables[table].append(stored)
		return stored

	def batch_write(self, table: str, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
		return [self.write(table, r) for r in records]

	def upsert(
		self, table: str, record: Dict[str, Any], on_conflict: Optional[List[str]] = None
	) -> Dict[str, Any]:
		self._ensure(table)
		if not on_conflict:
			return self.write(table, record)
		for idx, existing in enumerate(self._tables[table]):
			if all(existing.get(k) == record.get(k) for k in on_conflict):
				updated = {**existing, **record}
				if "id" not in updated:
					updated["id"] = existing.get("id")
				self._tables[table][idx] = updated
				return updated
		return self.write(table, record)

	# Read ops ----------------------------------------------------------
	def read(self, table: str, id_value: Any, id_column: str = "id") -> Optional[Dict[str, Any]]:
		self._ensure(table)
		for row in self._tables[table]:
			if row.get(id_column) == id_value:
				return row
		return None

	def query(
		self,
		table: str,
		filters: Optional[Dict[str, Any]] = None,
		limit: Optional[int] = None,
		order_by: Optional[str] = None,
		descending: bool = False,
		select: Optional[List[str]] = None,
	) -> List[Dict[str, Any]]:
		self._ensure(table)
		if __import__('os').environ.get('RAG_DEEP_DEBUG','0').lower() in ('1','true','yes'):
			try:
				print(f"[MEM TRACE] query table={table} filters={filters} limit={limit} order_by={order_by} desc={descending} select={select}")
			except Exception:
				pass
		results: List[Dict[str, Any]] = []
		for row in self._tables[table]:
			mismatch = False
			if filters:
				for k, v in filters.items():
					row_val = row.get(k)
					if isinstance(v, str) and "%" in v:
						# Case-insensitive % wildcard match
						if not self._wildcard_match(row_val, v):
							mismatch = True
							break
					elif row_val != v:
						mismatch = True
						break
			if mismatch:
				continue
			results.append(row)

		if order_by:
			results.sort(key=lambda r: r.get(order_by), reverse=descending)

		if select:
			results = [{k: r.get(k) for k in select} for r in results]

		if limit is not None:
			results = results[:limit]
		return results

	def get_columns(self, table: str) -> Optional[List[str]]:  # pragma: no cover
		self._ensure(table)
		rows = self._tables.get(table, [])
		if not rows:
			return []
		keys: Set[str] = set()
		for r in rows:
			keys.update(r.keys())
		return sorted(keys)


__all__ = ["InMemoryAdapter"]

