"""Supabase client dependency for gateway endpoints.

Provides a tenant-scoped Supabase client that respects RLS policies
by passing the user's JWT token as the Authorization header.
"""

from __future__ import annotations

import httpx
from typing import Any, Dict, List, Optional
from functools import lru_cache

from fastapi import Depends, HTTPException

from ..config import settings
from .auth import AuthUser, get_current_user


class SupabaseClient:
    """Lightweight Supabase REST client for gateway use.
    
    Uses httpx for async-compatible HTTP calls to Supabase REST API.
    All requests include the user's JWT for RLS enforcement.
    """
    
    def __init__(self, url: str, anon_key: str, user_jwt: str):
        self.base_url = url.rstrip("/")
        self.anon_key = anon_key
        self.user_jwt = user_jwt
        self._headers = {
            "apikey": anon_key,
            "Authorization": f"Bearer {user_jwt}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
    
    # ─────────────────────────────────────────────────────────────────
    # Query Builder
    # ─────────────────────────────────────────────────────────────────
    
    def _apply_filters(self, params: Dict[str, Any], filters: Optional[Dict[str, Any]] = None) -> None:
        if not filters:
            return
        for key, value in filters.items():
            if isinstance(value, tuple) and len(value) == 2:
                op, raw = value
                op = str(op).strip()
                if op == "in" and isinstance(raw, (list, tuple)):
                    joined = ",".join(str(v) for v in raw)
                    params[key] = f"in.({joined})"
                else:
                    params[key] = f"{op}.{raw}"
            else:
                params[key] = f"eq.{value}"

    async def select(
        self,
        table: str,
        columns: str = "*",
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        descending: bool = False,
        limit: Optional[int] = None,
        single: bool = False,
    ) -> List[Dict[str, Any]] | Dict[str, Any] | None:
        """Query rows from a table with optional filters.
        
        Args:
            table: Table name
            columns: Columns to select (default "*")
            filters: Dict of {column: value} for equality filters
            order_by: Column to order by
            descending: If True, order descending
            limit: Max rows to return
            single: If True, return single dict or None instead of list
            
        Returns:
            List of rows, or single row if single=True
        """
        url = f"{self.base_url}/rest/v1/{table}"
        params = {"select": columns}
        
        self._apply_filters(params, filters)
        
        if order_by:
            direction = "desc" if descending else "asc"
            params["order"] = f"{order_by}.{direction}"
        
        if limit:
            params["limit"] = str(limit)
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._headers, params=params)
            
        if response.status_code == 200:
            data = response.json()
            if single:
                return data[0] if data else None
            return data
        
        if response.status_code == 404:
            return [] if not single else None
            
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Supabase query failed: {response.text}"
        )
    
    async def select_one(
        self,
        table: str,
        id_value: str,
        id_column: str = "id",
        columns: str = "*",
    ) -> Optional[Dict[str, Any]]:
        """Get a single row by ID."""
        return await self.select(
            table=table,
            columns=columns,
            filters={id_column: id_value},
            limit=1,
            single=True,
        )
    
    async def insert(
        self,
        table: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Insert a single row and return the created record."""
        url = f"{self.base_url}/rest/v1/{table}"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=self._headers,
                json=data,
            )
        
        if response.status_code in (200, 201):
            result = response.json()
            return result[0] if isinstance(result, list) and result else result
        
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Supabase insert failed: {response.text}"
        )
    
    async def update(
        self,
        table: str,
        id_value: str,
        data: Dict[str, Any],
        id_column: str = "id",
    ) -> Dict[str, Any]:
        """Update a row by ID and return the updated record."""
        url = f"{self.base_url}/rest/v1/{table}"
        params = {id_column: f"eq.{id_value}"}
        
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                url,
                headers=self._headers,
                params=params,
                json=data,
            )
        
        if response.status_code in (200, 204):
            result = response.json() if response.content else {}
            return result[0] if isinstance(result, list) and result else result
        
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="Record not found")
        
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Supabase update failed: {response.text}"
        )
    
    async def delete(
        self,
        table: str,
        id_value: str,
        id_column: str = "id",
    ) -> bool:
        """Delete a row by ID. Returns True if successful."""
        url = f"{self.base_url}/rest/v1/{table}"
        params = {id_column: f"eq.{id_value}"}
        
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                url,
                headers=self._headers,
                params=params,
            )
        
        if response.status_code in (200, 204):
            return True
        
        if response.status_code == 404:
            return False
        
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Supabase delete failed: {response.text}"
        )
    
    async def count(
        self,
        table: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Count rows in a table with optional filters."""
        url = f"{self.base_url}/rest/v1/{table}"
        headers = {**self._headers, "Prefer": "count=exact"}
        params = {"select": "*"}
        
        self._apply_filters(params, filters)
        
        # HEAD request to get count from Content-Range header
        async with httpx.AsyncClient() as client:
            response = await client.head(url, headers=headers, params=params)
        
        if response.status_code == 200:
            content_range = response.headers.get("Content-Range", "")
            # Format: "0-9/100" or "*/0" for empty
            if "/" in content_range:
                total = content_range.split("/")[-1]
                return int(total) if total != "*" else 0
            return 0
        
        # Fallback: do a select and count
        data = await self.select(table, columns="id", filters=filters)
        return len(data) if isinstance(data, list) else 0


def get_supabase_client(
    user: AuthUser = Depends(get_current_user),
) -> SupabaseClient:
    """Dependency that provides a tenant-scoped Supabase client.
    
    The client uses the user's JWT token for all requests, ensuring
    RLS policies are properly enforced based on the user's tenant.
    """
    if not settings.SUPABASE_URL:
        raise HTTPException(status_code=500, detail="SUPABASE_URL not configured")
    if not settings.SUPABASE_ANON_KEY:
        raise HTTPException(status_code=500, detail="SUPABASE_ANON_KEY not configured")
    
    # Get the raw token from request context - we need to reconstruct it
    # Since we receive AuthUser, we need to pass through the original token
    # This is handled by extracting from the bearer scheme
    
    # For now, we'll need to get the token a different way
    # Let's create a separate dependency that captures both
    raise HTTPException(
        status_code=500,
        detail="Use get_supabase_client_with_token instead"
    )


async def get_supabase(
    request_token: str,
) -> SupabaseClient:
    """Create a Supabase client with the given JWT token."""
    return SupabaseClient(
        url=settings.SUPABASE_URL,
        anon_key=settings.SUPABASE_ANON_KEY,
        user_jwt=request_token,
    )


# Combined dependency for routes
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer_scheme = HTTPBearer(auto_error=True)


async def get_db(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    user: AuthUser = Depends(get_current_user),
) -> SupabaseClient:
    """Combined dependency that validates auth and returns Supabase client.
    
    Usage in routes:
        @router.get("/drafts")
        async def list_drafts(db: SupabaseClient = Depends(get_db)):
            return await db.select("drafts", filters={"status": "pending"})
    """
    if not settings.SUPABASE_URL:
        raise HTTPException(status_code=500, detail="SUPABASE_URL not configured")
    if not settings.SUPABASE_ANON_KEY:
        raise HTTPException(status_code=500, detail="SUPABASE_ANON_KEY not configured")
    
    return SupabaseClient(
        url=settings.SUPABASE_URL,
        anon_key=settings.SUPABASE_ANON_KEY,
        user_jwt=credentials.credentials,
    )
