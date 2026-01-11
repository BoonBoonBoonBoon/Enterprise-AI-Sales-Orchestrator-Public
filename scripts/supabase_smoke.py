"""Supabase connectivity smoke test.

Usage:
  python scripts/supabase_smoke.py [table]

Environment:
  SUPABASE_URL
  SUPABASE_SERVICE_KEY (or SUPABASE_KEY fallback)

It will attempt a simple select * limit 1 on the provided table (default 'leads').
No mutations are performed.
"""
from __future__ import annotations
import os, sys, json, time, pathlib

def _load_env_file():
    """Lightweight .env loader (avoids extra dependency on python-dotenv).

    Only populates variables that are not already set in the process env.
    Lines beginning with '#' are ignored. Quotes are not stripped (keep simple).
    """
    env_path = pathlib.Path('.env')
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding='utf-8').splitlines():
        if not line.strip() or line.strip().startswith('#'):
            continue
        if '=' not in line:
            continue
        key, val = line.split('=', 1)
        key = key.strip()
        val = val.strip()
        if key and key not in os.environ:
            os.environ[key] = val

def main():
    # Attempt local .env bootstrap first
    _load_env_file()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
    table = sys.argv[1] if len(sys.argv) > 1 else "leads"
    if not url or not key:
        print("MISSING_ENV", json.dumps({"have_url": bool(url), "have_key": bool(key)}))
        return 2
    try:
        start = time.time()
        from supabase import create_client  # type: ignore
        client = create_client(url, key)
        resp = client.table(table).select("*").limit(1).execute()
        data = getattr(resp, "data", None)
        dur = (time.time() - start) * 1000
        if isinstance(data, list):
            print("OK", json.dumps({"table": table, "row_count": len(data), "ms": round(dur,2)}))
            return 0
        else:
            print("NO_DATA", json.dumps({"table": table, "ms": round(dur,2)}))
            return 0
    except ImportError:
        print("MISSING_PACKAGE", json.dumps({"pip_install": "pip install supabase"}))
        return 3
    except Exception as e:
        print("ERROR", json.dumps({"error": str(e), "table": table}))
        return 1

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
