from typing import Dict, Any, List, Optional


class SupabaseDBAdapter:
    """DBWriteAdapter implementation backed by Supabase.

    This adapter imports the `supabase` package at runtime. If the package is not
    installed, attempting to construct the adapter will raise an informative ImportError.
    Purpose: Acts as a thin, pluggable abstraction that hides the database client details 
    and exposes simple write primitives (write, batch_write, upsert) the rest of the app calls.
      """

    def __init__(self, url: str, key: str, client: Optional[Any] = None):
        # import here so package is optional for users who don't need Supabase
        try:
            from supabase import create_client
        except Exception as e:
            raise ImportError(
                "supabase client is required for SupabaseDBAdapter but is not installed. "
                "Install with `pip install supabase` or pass an existing client via `client=`."
            ) from e

        # keep url/key for an HTTP fallback if needed
        self.url = url
        self.key = key

        if client is not None:
            self.client = client
        else:
            # create_client typically sets both `apikey` and `Authorization: Bearer` headers
            # but some environments or versions may behave differently; keep url/key for fallback.
            self.client = create_client(url, key)

    def write(self, table: str, record: Dict[str, Any]) -> Dict[str, Any]:
        resp = self.client.table(table).insert(record).execute()
        # Supabase client returns a dict-like response; try to extract inserted row
        data = None
        if hasattr(resp, "data"):
            data = resp.data
        elif isinstance(resp, dict):
            data = resp.get("data")

        if isinstance(data, list) and len(data) > 0:
            return data[0]

        return {"status": "ok", "raw": data}

    def batch_write(self, table: str, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        resp = self.client.table(table).insert(records).execute()
        data = None
        if hasattr(resp, "data"):
            data = resp.data
        elif isinstance(resp, dict):
            data = resp.get("data")

        if isinstance(data, list):
            return data

        return []

    def upsert(self, table: str, record: Dict[str, Any], on_conflict: Optional[List[str]] = None) -> Dict[str, Any]:
        """Perform an upsert using Supabase's upsert API.

        `on_conflict` is a list of column names to use for conflict resolution. If not
        provided, behavior falls back to insert.
        """
        # supabase-py supports `upsert`; the exact API surface may vary between versions.
        resp = None
        try:
            if on_conflict:
                resp = self.client.table(table).upsert(record, on_conflict=on_conflict).execute()
            else:
                resp = self.client.table(table).insert(record).execute()
        except TypeError:
            try:
                resp = self.client.table(table).upsert(record).execute()
            except Exception:
                try:
                    resp = self.client.table(table).insert(record).execute()
                except Exception:
                    resp = None
        except Exception:
            # something went wrong at the client layer; we'll try an HTTP REST fallback below
            resp = None

        data = None

        # If the client returned a response, try to extract data and also detect errors
        client_error = None
        if resp is not None:
            if hasattr(resp, "error") and resp.error:
                client_error = resp.error
            elif isinstance(resp, dict) and (resp.get("error") or resp.get("message")):
                client_error = resp.get("error") or resp.get("message")

            if hasattr(resp, "data"):
                data = resp.data
            elif isinstance(resp, dict):
                data = resp.get("data")

            if client_error:
                # try HTTP fallback if the error looks like a permission or other server-side issue
                try:
                    return self._rest_upsert(table, record, on_conflict=on_conflict)
                except Exception:
                    raise

        # If we have good data from the client, return it
        if isinstance(data, list) and len(data) > 0:
            return data[0]

        # If client produced no usable response, attempt HTTP fallback
        try:
            return self._rest_upsert(table, record, on_conflict=on_conflict)
        except Exception:
            return {"status": "ok", "raw": data}

    def _rest_upsert(self, table: str, record: Dict[str, Any], on_conflict: Optional[List[str]] = None) -> Dict[str, Any]:
        """Fallback directly to Supabase REST (PostgREST) using `requests`.

        This ensures both `apikey` and `Authorization: Bearer <key>` headers are sent
        which Supabase expects for service-role authenticated server-side requests.
        """
        try:
            import requests
        except Exception as e:
            raise ImportError("requests is required for HTTP fallback in SupabaseDBAdapter") from e

        url = self.url.rstrip("/") + f"/rest/v1/{table}"
        headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

        params = {}
        if on_conflict:
            params["on_conflict"] = ",".join(on_conflict)

        import json

        body = json.dumps([record])

        resp = requests.post(url, headers=headers, params=params, data=body, timeout=15)
        if resp.status_code in (200, 201):
            try:
                j = resp.json()
                if isinstance(j, list) and len(j) > 0:
                    return j[0]
                return {"status": "ok", "raw": j}
            except Exception:
                return {"status": "ok", "raw": resp.text}

        # raise a helpful error with status and body
        raise RuntimeError({"status_code": resp.status_code, "text": resp.text})


__all__ = ["SupabaseDBAdapter"]
