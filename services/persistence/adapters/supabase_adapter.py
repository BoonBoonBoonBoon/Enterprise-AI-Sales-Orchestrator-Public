"""Supabase adapter implementation.

Implements the PersistenceAdapter contract using the official Supabase SDK
with a REST fallback. This adapter is intentionally thin: validation,
allowlist enforcement, and instrumentation live in PersistenceService.

Notes
-----
- Query supports equality and ilike (case-insensitive substring) via `%` in
	the filter value. This mirrors tests and makes wildcard domain/email search
	work consistently between SDK and REST paths.
"""

from __future__ import annotations

import os
import socket
from urllib.parse import urlparse
from typing import Dict, Any, List, Optional


class SupabaseAdapter:
	def __init__(self, url: str, key: str, client: Optional[Any] = None, anon_key: Optional[str] = None):
		url = (url or "").strip()
		key = (key or "").strip()
		anon_key = anon_key.strip() if isinstance(anon_key, str) else anon_key

		try:
			from supabase import create_client  # type: ignore
		except Exception as e:  # pragma: no cover
			raise ImportError(
				"supabase client not installed. Install via `pip install supabase`"
			) from e

		# Fail fast on obvious SUPABASE_URL misconfiguration (e.g., deleted project ref / NXDOMAIN).
		# Can be disabled for offline/dev environments by setting SUPABASE_SKIP_DNS_CHECK=1.
		skip_dns_check = os.environ.get("SUPABASE_SKIP_DNS_CHECK", "0").lower() in ("1", "true", "yes")
		if not skip_dns_check:
			host = urlparse(url).hostname
			if host:
				try:
					socket.getaddrinfo(host, 443)
				except OSError as e:
					raise ValueError(
						f"SUPABASE_URL hostname does not resolve: {host}. "
						"Verify your Supabase project URL (Settings → API) or set SUPABASE_SKIP_DNS_CHECK=1."
					) from e

		self.url = url.rstrip("/")
		self.key = key
		self.anon_key = anon_key  # For custom JWT authentication pattern
		self.client = client or create_client(url, key)
		# Adapter capability metadata; consulted by higher-level planners (RAG, etc.)
		self.capabilities = {
			"equality_filters": True,
			"ordering": True,
			"limit": True,
			"projections": True,
			"ilike": True,
			"range_operators": False,
			"in_operator": False,
		}

	# -------------------------------------------------- Write Ops ---------
	def write(self, table: str, record: Dict[str, Any]) -> Dict[str, Any]:
		# If using custom JWT (anon_key provided), use REST API
		if self.anon_key:
			return self._rest_write(table, record)
		# Otherwise use SDK
		resp = self.client.table(table).insert(record).execute()
		data = getattr(resp, "data", None) if not isinstance(resp, dict) else resp.get("data")
		if isinstance(data, list) and data:
			return data[0]
		return {"status": "ok", "raw": data}

	def batch_write(self, table: str, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
		# If using custom JWT (anon_key provided), use REST API
		if self.anon_key:
			return self._rest_batch_write(table, records)
		# Otherwise use SDK
		resp = self.client.table(table).insert(records).execute()
		data = getattr(resp, "data", None) if not isinstance(resp, dict) else resp.get("data")
		return data if isinstance(data, list) else []

	def upsert(
		self, table: str, record: Dict[str, Any], on_conflict: Optional[List[str]] = None
	) -> Dict[str, Any]:
		# If using custom JWT (anon_key provided), use REST API
		if self.anon_key:
			return self._rest_upsert(table, record, on_conflict)
		# Otherwise use SDK
		resp = None
		try:
			if on_conflict:
				resp = self.client.table(table).upsert(record, on_conflict=on_conflict).execute()
			else:
				resp = self.client.table(table).upsert(record).execute()
		except TypeError:
			resp = self.client.table(table).insert(record).execute()
		data = getattr(resp, "data", None) if not isinstance(resp, dict) else resp.get("data")
		if isinstance(data, list) and data:
			return data[0]
		return {"status": "ok", "raw": data}

	def delete(self, table: str, id_value: str, id_column: str = "id") -> Dict[str, Any]:
		"""Delete a record from a table by ID.
		
		Args:
			table: Table name
			id_value: Value of the ID to delete
			id_column: Name of the ID column (default: "id")
			
		Returns:
			dict with status or error
		"""
		try:
			# Use REST API if anon_key is provided (custom JWT pattern)
			if self.anon_key:
				return self._rest_delete(table, id_value, id_column)
			
			# Otherwise use SDK
			result = self.client.table(table).delete().eq(id_column, id_value).execute()
			return {"status": "ok", "deleted_count": len(result.data) if result.data else 0}
		except Exception as e:
			return {"error": str(e)}

	# -------------------------------------------------- Read Ops ----------
	def read(self, table: str, id_value: Any, id_column: str = "id") -> Optional[Dict[str, Any]]:
		try:
			resp = self.client.table(table).select("*").eq(id_column, id_value).limit(1).execute()
			data = getattr(resp, "data", None) if not isinstance(resp, dict) else resp.get("data")
			if isinstance(data, list) and data:
				return data[0]
			return None
		except Exception:
			return self._rest_read(table, id_value, id_column)

	def query(
		self,
		table: str,
		filters: Optional[Dict[str, Any]] = None,
		limit: Optional[int] = None,
		order_by: Optional[str] = None,
		descending: bool = False,
		select: Optional[List[str]] = None,
	) -> List[Dict[str, Any]]:
		"""Query rows with basic filters/ordering/limits.

		Behavior
		- String filter values containing `%` use ilike; else equality.
		- order_by + descending map to Supabase order options.
		- select projects columns if provided.
		- On SDK errors, falls back to REST with equivalent semantics.
		"""
		try:
			projection = "*" if not select else ",".join(select)
			q = self.client.table(table).select(projection)
			if filters:
				for k, v in filters.items():
					# Use ilike when pattern contains SQL wildcard %
					if isinstance(v, str) and "%" in v:
						q = q.ilike(k, v)
					else:
						q = q.eq(k, v)
			if order_by:
				q = q.order(order_by, desc=descending)
			if limit is not None:
				q = q.limit(limit)
			if __import__('os').environ.get('RAG_DEEP_DEBUG','0').lower() in ('1','true','yes'):
				try:
					print(f"[SUPABASE TRACE] query sdk table={table} filters={filters} limit={limit} order_by={order_by} desc={descending} select={select}")
				except Exception:
					pass
			resp = q.execute()
			data = getattr(resp, "data", None) if not isinstance(resp, dict) else resp.get("data")
			return data if isinstance(data, list) else []
		except Exception:
			return self._rest_query(
				table,
				filters=filters,
				limit=limit,
				order_by=order_by,
				descending=descending,
				select=select,
			)

	def get_columns(self, table: str) -> Optional[List[str]]:  # pragma: no cover
		try:
			resp = self.client.table(table).select("*").limit(1).execute()
			data = getattr(resp, "data", None) if not isinstance(resp, dict) else resp.get("data")
			if isinstance(data, list) and data:
				return sorted(list(data[0].keys()))
		except Exception:
			return None
		return None

	# -------------------------------------------------- REST Fallbacks ----
	def _rest_headers(self) -> Dict[str, str]:
		# If anon_key is provided, use it for apikey and key for Authorization (custom JWT pattern)
		if self.anon_key:
			return {
				"apikey": self.anon_key,
				"Authorization": f"Bearer {self.key}",
				"Accept": "application/json",
				"Content-Type": "application/json",
			}
		# Otherwise use the same key for both (standard pattern)
		return {
			"apikey": self.key,
			"Authorization": f"Bearer {self.key}",
			"Accept": "application/json",
			"Content-Type": "application/json",
		}

	def _rest_read(self, table: str, id_value: Any, id_column: str) -> Optional[Dict[str, Any]]:
		import requests, json  # type: ignore

		url = f"{self.url}/rest/v1/{table}"
		params = {id_column: f"eq.{id_value}", "limit": 1}
		r = requests.get(url, headers=self._rest_headers(), params=params, timeout=15)
		if r.status_code == 200:
			try:
				data = r.json()
				if isinstance(data, list) and data:
					return data[0]
			except Exception:
				return None
		return None

	def _rest_query(
		self,
		table: str,
		filters: Optional[Dict[str, Any]] = None,
		limit: Optional[int] = None,
		order_by: Optional[str] = None,
		descending: bool = False,
		select: Optional[List[str]] = None,
	) -> List[Dict[str, Any]]:
		import requests  # type: ignore

		url = f"{self.url}/rest/v1/{table}"
		params: Dict[str, Any] = {}
		if select:
			params["select"] = ",".join(select)
		if filters:
			for k, v in filters.items():
				if isinstance(v, str) and "%" in v:
					# PostgREST uses * as wildcard for like/ilike operators
					params[k] = f"ilike.{v.replace('%','*')}"
				else:
					params[k] = f"eq.{v}"
		if limit is not None:
			params["limit"] = limit
		if order_by:
			params["order"] = f"{order_by}.{'desc' if descending else 'asc'}"
		if __import__('os').environ.get('RAG_DEEP_DEBUG','0').lower() in ('1','true','yes'):
			try:
				print(f"[SUPABASE TRACE] query rest url={url} params={params}")
			except Exception:
				pass
		r = requests.get(url, headers=self._rest_headers(), params=params, timeout=15)
		if r.status_code == 200:
			try:
				data = r.json()
				return data if isinstance(data, list) else []
			except Exception:
				return []
		return []

	def _rest_write(self, table: str, record: Dict[str, Any]) -> Dict[str, Any]:
		import requests, json  # type: ignore

		url = f"{self.url}/rest/v1/{table}"
		r = requests.post(url, headers=self._rest_headers(), json=record, timeout=15)
		if r.status_code in [200, 201]:
			try:
				data = r.json()
				if isinstance(data, list) and data:
					return data[0]
				return {"status": "ok", "raw": data}
			except Exception:
				return {"status": "ok"}
		raise Exception(f"Write failed: {r.status_code} - {r.text[:200]}")

	def _rest_batch_write(self, table: str, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
		import requests, json  # type: ignore

		url = f"{self.url}/rest/v1/{table}"
		r = requests.post(url, headers=self._rest_headers(), json=records, timeout=15)
		if r.status_code in [200, 201]:
			try:
				data = r.json()
				return data if isinstance(data, list) else []
			except Exception:
				return []
		return []

	def _rest_upsert(
		self, table: str, record: Dict[str, Any], on_conflict: Optional[List[str]] = None
	) -> Dict[str, Any]:
		import requests, json  # type: ignore

		url = f"{self.url}/rest/v1/{table}"
		headers = self._rest_headers()
		# return=representation ensures we get the inserted/updated record back (including id)
		headers["Prefer"] = "return=representation,resolution=merge-duplicates"
		if on_conflict:
			headers["Prefer"] += f",on_conflict={','.join(on_conflict)}"
		
		r = requests.post(url, headers=headers, json=record, timeout=15)
		if r.status_code in [200, 201]:
			try:
				data = r.json()
				if isinstance(data, list) and data:
					return data[0]
				return {"status": "ok", "raw": data}
			except Exception:
				return {"status": "ok"}
		# Fallback to regular insert if upsert fails
		return self._rest_write(table, record)

	def _rest_delete(self, table: str, id_value: str, id_column: str = "id") -> Dict[str, Any]:
		"""Delete using REST API with custom JWT."""
		import requests  # type: ignore

		try:
			url = f"{self.url}/rest/v1/{table}?{id_column}=eq.{id_value}"
			headers = self._rest_headers()
			headers["Prefer"] = "return=representation"
			
			response = requests.delete(url, headers=headers, timeout=10)
			
			if response.status_code in (200, 204):
				return {"status": "ok", "deleted_count": 1}
			else:
				return {"error": response.text, "status_code": response.status_code}
		except Exception as e:
			return {"error": str(e)}


__all__ = ["SupabaseAdapter"]

