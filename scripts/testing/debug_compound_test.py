#!/usr/bin/env python
"""Debug script to test compound persistence with HybridSupabaseRedisAdapter."""
import os
import sys
import uuid
import json
import redis as redis_lib

sys.path.insert(0, '/app')

from services.persistence.adapters.supabase_adapter import SupabaseAdapter
from tiers.tier_3.persistence_agent.compound_handler import CompoundPayload, execute_compound
from typing import Dict, Any, List, Optional

# Copy the adapters from consumer.py
class RedisHashAdapter:
    """Simple Redis-based persistence adapter using HSET/HGET."""

    def __init__(self, redis_url: str, tenant_id: str):
        self.redis = redis_lib.from_url(redis_url)
        self.tenant_id = tenant_id

    def _key(self, table: str) -> str:
        return f"{self.tenant_id}:cache:{table}"

    def _all_rows(self, table: str) -> List[Dict[str, Any]]:
        data = self.redis.hgetall(self._key(table))
        rows = []
        for v in data.values():
            try:
                rows.append(json.loads(v))
            except Exception:
                pass
        return rows

    def write(self, table: str, record: Dict[str, Any]) -> Dict[str, Any]:
        stored = {**record}
        stored.setdefault("id", str(uuid.uuid4()))
        self.redis.hset(self._key(table), stored["id"], json.dumps(stored))
        return stored

    def upsert(self, table: str, record: Dict[str, Any], on_conflict: Optional[List[str]] = None) -> Dict[str, Any]:
        if not on_conflict:
            return self.write(table, record)
        for existing in self._all_rows(table):
            if all(existing.get(k) == record.get(k) for k in on_conflict):
                updated = {**existing, **record}
                updated.setdefault("id", existing.get("id"))
                self.redis.hset(self._key(table), updated["id"], json.dumps(updated))
                return updated
        return self.write(table, record)


class HybridSupabaseRedisAdapter:
    """Supabase primary adapter with Redis cache fallback."""

    def __init__(self, primary: Any, cache: RedisHashAdapter):
        self.primary = primary
        self.cache = cache

    def write(self, table: str, record: Dict[str, Any]) -> Dict[str, Any]:
        try:
            result = self.primary.write(table, record)
            self.cache.write(table, result or record)
            return result
        except Exception as exc:
            print(f"HYBRID: Supabase write failed, using Redis cache: {exc}")
            return self.cache.write(table, record)

    def upsert(self, table: str, record: Dict[str, Any], on_conflict: Optional[List[str]] = None) -> Dict[str, Any]:
        try:
            result = self.primary.upsert(table, record, on_conflict=on_conflict)
            self.cache.write(table, result or record)
            return result
        except Exception as exc:
            print(f"HYBRID: Supabase upsert failed, using Redis cache: {exc}")
            return self.cache.upsert(table, record, on_conflict=on_conflict)


# Monkey-patch to see full request details
original_rest_upsert = SupabaseAdapter._rest_upsert
def debug_rest_upsert(self, table, record, on_conflict=None):
    import requests
    url = self.url + '/rest/v1/' + table
    headers = self._rest_headers()
    headers['Prefer'] = 'return=representation,resolution=merge-duplicates'
    params = {}
    if on_conflict:
        params['on_conflict'] = ','.join(on_conflict)
    print(f'DEBUG URL: {url}')
    print(f'DEBUG params: {params}')
    print(f'DEBUG record keys: {list(record.keys()) if record else None}')
    print(f'DEBUG staging_lead_id value: {record.get("staging_lead_id", "N/A")}')
    r = requests.post(url, headers=headers, params=params or None, json=record, timeout=15)
    print(f'DEBUG response: {r.status_code} {r.text[:300]}')
    return original_rest_upsert(self, table, record, on_conflict)

SupabaseAdapter._rest_upsert = debug_rest_upsert

# Setup adapters like consumer.py does
supabase_key = os.getenv('SUPABASE_PERSISTENCE_JWT') or os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_KEY')
anon_key = os.getenv('SUPABASE_ANON_KEY')
url = os.getenv('SUPABASE_URL')
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
tenant_id = 'agentic-dev'

supabase_adapter = SupabaseAdapter(url, supabase_key, anon_key=anon_key)
cache_adapter = RedisHashAdapter(redis_url=redis_url, tenant_id=tenant_id)
adapter = HybridSupabaseRedisAdapter(primary=supabase_adapter, cache=cache_adapter)

conv_id = str(uuid.uuid4())

# Build payload with proper $ref syntax
payload = CompoundPayload(
    steps=[
        {
            'step_name': 'staging_lead',
            'table': 'staging_leads',
            'operation': 'upsert',
            'data': {
                'email': f'debug3_{uuid.uuid4().hex[:8]}@example.com',
                'source': 'inbound_email',
                'client_id': '93d28de3-2835-52f3-b2ef-c2eb8a2ac09b'
            },
            'match_on': ['client_id', 'email']
        },
        {
            'step_name': 'staging_conversation',
            'table': 'staging_conversations',
            'operation': 'upsert',
            'data': {
                'id': conv_id,
                'staging_lead_id': '$ref:staging_lead.id',  # Reference to step 1 output
                'subject': 'debug3 test',
                'channel': 'email',
                'status': 'open',
                'metadata': {}
            },
            'match_on': ['id']
        }
    ]
)

result = execute_compound(payload, adapter)
print('=' * 60)
print(f'Final status: {result.success}')
for sr in result.step_results:
    print(f'  {sr.step_name}: {sr.status} - {sr.error or "ok"}')
