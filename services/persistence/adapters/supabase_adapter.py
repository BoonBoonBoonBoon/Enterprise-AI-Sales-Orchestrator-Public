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
		# If using custom JWT auth, the Supabase SDK should still be initialized with a real API key
		# (anon/service key). The JWT is used as the Authorization bearer token in REST fallback.
		sdk_key = anon_key or key
		self.client = client or create_client(url, sdk_key)
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
		self._rest_session = None

	# -------------------------------------------------- Write Ops ---------
	def rpc(self, function: str, params: Optional[Dict[str, Any]] = None) -> Any:
		"""Call a Postgres function via Supabase RPC."""
		if self.anon_key:
			return self._rest_rpc(function, params or {})
		resp = self.client.rpc(function, params or {}).execute()
		data = getattr(resp, "data", None) if not isinstance(resp, dict) else resp.get("data")
		return data

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
		# Convert on_conflict list to comma-separated string for SDK
		on_conflict_str = ",".join(on_conflict) if on_conflict else ""
		try:
			if on_conflict_str:
				resp = self.client.table(table).upsert(record, on_conflict=on_conflict_str).execute()
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
		# In custom JWT mode, always use REST so Authorization uses the JWT bearer token.
		if self.anon_key:
			return self._rest_read(table, id_value, id_column)
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
		# In custom JWT mode, always use REST so Authorization uses the JWT bearer token.
		if self.anon_key:
			return self._rest_query(
				table,
				filters=filters,
				limit=limit,
				order_by=order_by,
				descending=descending,
				select=select,
			)
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
	def _get_rest_session(self):
		if self._rest_session is not None:
			return self._rest_session
		import requests  # type: ignore
		from requests.adapters import HTTPAdapter  # type: ignore
		try:  # pragma: no cover - fallback import for older vendored urllib3
			from urllib3.util.retry import Retry  # type: ignore
		except Exception:  # pragma: no cover
			from requests.packages.urllib3.util.retry import Retry  # type: ignore

		retries = int(os.environ.get("SUPABASE_REST_RETRIES", "3"))
		backoff = float(os.environ.get("SUPABASE_REST_BACKOFF", "0.5"))
		status_forcelist = (429, 500, 502, 503, 504)
		allowed_methods = frozenset([
			"HEAD",
			"GET",
			"POST",
			"PUT",
			"DELETE",
			"OPTIONS",
			"TRACE",
			"PATCH",
		])
		retry = Retry(
			total=retries,
			connect=retries,
			read=retries,
			status=retries,
			backoff_factor=backoff,
			status_forcelist=status_forcelist,
			allowed_methods=allowed_methods,
			raise_on_status=False,
		)
		adapter = HTTPAdapter(max_retries=retry)
		session = requests.Session()
		session.mount("http://", adapter)
		session.mount("https://", adapter)
		self._rest_session = session
		return session

	def _rest_timeout(self, kind: str = "default") -> float:
		default_timeout = float(os.environ.get("SUPABASE_REST_TIMEOUT_S", "15"))
		if kind == "rpc":
			return float(os.environ.get("SUPABASE_REST_RPC_TIMEOUT_S", str(default_timeout)))
		return default_timeout

	def _rest_rpc(self, function: str, params: Dict[str, Any]) -> Any:
		url = f"{self.url}/rest/v1/rpc/{function}"
		session = self._get_rest_session()
		r = session.post(
			url,
			headers=self._rest_headers(),
			json=params,
			timeout=self._rest_timeout("rpc"),
		)
		if r.status_code in (200, 201, 204):
			try:
				return r.json()
			except Exception:
				return None
		raise ValueError(f"RPC {function} failed ({r.status_code}): {r.text}")
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
		url = f"{self.url}/rest/v1/{table}"
		params = {id_column: f"eq.{id_value}", "limit": 1}
		session = self._get_rest_session()
		r = session.get(url, headers=self._rest_headers(), params=params, timeout=self._rest_timeout())
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
		session = self._get_rest_session()
		r = session.get(url, headers=self._rest_headers(), params=params, timeout=self._rest_timeout())
		if r.status_code == 200:
			try:
				data = r.json()
				return data if isinstance(data, list) else []
			except Exception:
				return []
		return []

	def _rest_write(self, table: str, record: Dict[str, Any]) -> Dict[str, Any]:
		url = f"{self.url}/rest/v1/{table}"
		headers = self._rest_headers()
		# Ensure we get the inserted row back (including id) for FK chaining.
		headers["Prefer"] = "return=representation"
		session = self._get_rest_session()
		r = session.post(url, headers=headers, json=record, timeout=self._rest_timeout())
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
		url = f"{self.url}/rest/v1/{table}"
		headers = self._rest_headers()
		# Ensure we get inserted rows back (including ids) for downstream reference resolution.
		headers["Prefer"] = "return=representation"
		session = self._get_rest_session()
		r = session.post(url, headers=headers, json=records, timeout=self._rest_timeout())
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
		url = f"{self.url}/rest/v1/{table}"
		headers = self._rest_headers()
		# return=representation ensures we get the inserted/updated record back (including id)
		headers["Prefer"] = "return=representation,resolution=merge-duplicates"
		params: Dict[str, Any] = {}
		# PostgREST expects on_conflict as a query parameter, not in the Prefer header.
		if on_conflict:
			params["on_conflict"] = ",".join(on_conflict)
		session = self._get_rest_session()
		r = session.post(
			url,
			headers=headers,
			params=params or None,
			json=record,
			timeout=self._rest_timeout(),
		)
		if r.status_code in [200, 201]:
			try:
				data = r.json()
				if isinstance(data, list) and data:
					return data[0]
				return {"status": "ok", "raw": data}
			except Exception:
				return {"status": "ok"}
		raise Exception(f"Upsert failed: {r.status_code} - {r.text[:200]}")

	def _rest_delete(self, table: str, id_value: str, id_column: str = "id") -> Dict[str, Any]:
		"""Delete using REST API with custom JWT."""
		try:
			url = f"{self.url}/rest/v1/{table}?{id_column}=eq.{id_value}"
			headers = self._rest_headers()
			headers["Prefer"] = "return=representation"
			session = self._get_rest_session()
			response = session.delete(url, headers=headers, timeout=self._rest_timeout())
			
			if response.status_code in (200, 204):
				return {"status": "ok", "deleted_count": 1}
			else:
				return {"error": response.text, "status_code": response.status_code}
		except Exception as e:
			return {"error": str(e)}


__all__ = ["SupabaseAdapter"]

