# Troubleshooting

Common errors and solutions when running the Agentic System.

## Quick Diagnosis

```powershell
# Check all systems
& ".venv/Scripts/python.exe" -m scripts.diagnostics.system_check
```

## Connection Errors

### Redis Connection Refused

**Error:**

```
ConnectionError: Error 111 connecting to localhost:6379. Connection refused.
```

**Solutions:**

1. **Start Redis:**

   ```powershell
   docker run -d --name redis -p 6379:6379 redis:7-alpine
   ```

2. **Check if Redis is running:**

   ```powershell
   docker ps | Select-String redis
   ```

3. **Verify REDIS_URL:**
   ```powershell
   echo $env:REDIS_URL
   # Should be: redis://localhost:6379/0
   ```

---

### Supabase Connection Failed

**Error:**

```
APIError: Invalid API key
```

**Solutions:**

1. **Verify credentials in `.env`:**

   ```bash
   SUPABASE_URL=https://YOUR-PROJECT.supabase.co
   SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIs...
   ```

2. **Check key is anon key, not service role:**

   - Go to Supabase Dashboard → Settings → API
   - Copy "anon public" key

3. **Test connection:**
   ```powershell
   & ".venv/Scripts/python.exe" -c "from services.persistence.supabase_adapter import SupabaseAdapter; print(SupabaseAdapter('agent_reader'))"
   ```

---

### OpenAI API Key Invalid

**Error:**

```
openai.AuthenticationError: Invalid API key provided
```

**Solutions:**

1. **Check key format** — should start with `sk-`
2. **No trailing whitespace** in `.env`
3. **Verify at** [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
4. **Check billing** — ensure account has credits

---

## Import/Module Errors

### ModuleNotFoundError: No module named 'tiers'

**Error:**

```
ModuleNotFoundError: No module named 'tiers'
```

**Solutions:**

1. **Run from project root:**

   ```powershell
   cd "C:\Users\Elliot\Desktop\Agency Files\Important\Technicals\Agentic System"
   ```

2. **Activate virtual environment:**

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

3. **Use module syntax:**
   ```powershell
   & ".venv/Scripts/python.exe" -m tiers.tier_3.rag_agent.consumer
   # NOT: python tiers/tier_3/rag_agent/consumer.py
   ```

---

### Import Error: Cannot import 'settings'

**Error:**

```
ImportError: cannot import name 'settings' from 'config.settings'
```

**Solutions:**

1. **Ensure `.env` exists:**

   ```powershell
   Test-Path .env
   ```

2. **Install python-dotenv:**

   ```powershell
   pip install python-dotenv
   ```

3. **Load dotenv before imports:**
   ```python
   from dotenv import load_dotenv
   load_dotenv()
   from config.settings import settings
   ```

---

## Stream/Consumer Issues

### Consumer Not Receiving Messages

**Symptoms:** Consumer runs but never processes tasks.

**Solutions:**

1. **Verify stream name matches:**

   ```powershell
   # Check what consumer is listening on
   # Should see: "Listening on agentic-dev:agents:rag:tasks"
   ```

2. **Check TENANT_ID consistency:**

   ```powershell
   echo $env:TENANT_ID
   # Should match task publisher
   ```

3. **Verify messages exist:**

   ```powershell
   & ".venv/Scripts/python.exe" -c "
   from services.redis.client import get_redis_client
   r = get_redis_client()
   print(r.xlen('agentic-dev:agents:rag:tasks'))
   "
   ```

4. **Check consumer group:**
   ```powershell
   & ".venv/Scripts/python.exe" -c "
   from services.redis.client import get_redis_client
   r = get_redis_client()
   print(r.xinfo_groups('agentic-dev:agents:rag:tasks'))
   "
   ```

---

### Message Stuck in Pending

**Symptoms:** Messages never acknowledged, consumer keeps retrying.

**Solutions:**

1. **Check pending messages:**

   ```powershell
   & ".venv/Scripts/python.exe" -c "
   from services.redis.client import get_redis_client
   r = get_redis_client()
   print(r.xpending('agentic-dev:agents:rag:tasks', 'rag-group'))
   "
   ```

2. **Manually acknowledge (debug only):**

   ```python
   r.xack('stream-name', 'group-name', 'message-id')
   ```

3. **Check for processing errors** in consumer logs.

---

### Stream Key Mismatch

**Error:**

```
NOGROUP No such key 'agentic-dev:agents:rag:tasks' or consumer group 'rag-group'
```

**Solutions:**

1. **Create the consumer group:**

   ```python
   from services.redis.client import get_redis_client
   r = get_redis_client()
   r.xgroup_create('agentic-dev:agents:rag:tasks', 'rag-group', mkstream=True)
   ```

2. **Verify stream naming convention:**
   - Manager: `{tenant}:manager:tasks`
   - Orchestrators: `{tenant}:orchestrators:{name}:tasks`
   - Agents: `{tenant}:agents:{name}:tasks`

---

## Database Errors

### RLS Policy Violation

**Error:**

```
PostgrestAPIError: new row violates row-level security policy
```

**Solutions:**

1. **Check tenant_id matches JWT:**

   ```python
   # Ensure task includes correct tenant_id
   task = {
       "tenant_id": "agentic-dev",  # Must match adapter
       ...
   }
   ```

2. **Verify role permissions:**

   - `agent_reader` → SELECT only
   - `agent_writer` → CRUD operations

3. **Check table has RLS enabled:**
   ```sql
   SELECT tablename, rowsecurity FROM pg_tables WHERE schemaname = 'public';
   ```

---

### Foreign Key Violation

**Error:**

```
ForeignKeyViolation: insert or update on table "leads" violates foreign key constraint
```

**Solutions:**

1. **Insert in correct order:**

   ```
   clients → campaigns → leads → conversations → messages
   ```

2. **Verify parent record exists:**

   ```python
   adapter.read("clients", client_id)  # Must exist first
   ```

3. **Check for valid UUIDs** — not placeholder strings.

---

### Null Constraint Violation (metadata)

**Error:**

```
NotNullViolation: null value in column "metadata" violates not-null constraint
```

**Solution:**

Always include metadata field:

```python
adapter.write("messages", {
    "content": "Hello",
    "metadata": {}  # Required, even if empty
})
```

---

## Performance Issues

### Slow Consumer Processing

**Symptoms:** Tasks take >5 seconds to process.

**Solutions:**

1. **Add logging to identify bottleneck:**

   ```python
   import time
   start = time.time()
   # ... operation ...
   print(f"Operation took {time.time() - start:.2f}s")
   ```

2. **Check LLM latency** — GPT-4 can be slow
3. **Check database queries** — add indexes if needed
4. **Consider batch processing** for bulk operations

---

### Memory Growing Unbounded

**Symptoms:** Consumer memory usage grows over time.

**Solutions:**

1. **Check for retained references:**

   ```python
   import gc
   gc.collect()
   ```

2. **Use streaming for large responses:**

   ```python
   for chunk in llm.stream(prompt):
       process(chunk)
   ```

3. **Limit batch sizes** in database queries.

---

## Getting Help

If you're still stuck:

1. **Check logs** with `LOG_LEVEL=DEBUG`
2. **Search existing issues** on GitHub
3. **Run diagnostics:**
   ```powershell
   & ".venv/Scripts/python.exe" -m scripts.diagnostics.system_check
   ```
4. **Include in bug reports:**
   - Error message (full traceback)
   - Steps to reproduce
   - Environment (OS, Python version)
   - Relevant config (redact secrets)
