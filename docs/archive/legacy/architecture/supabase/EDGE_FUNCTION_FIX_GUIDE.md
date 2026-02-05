# Fix the Edge Function - Manual Steps

## Problem

The `generate-agent-jwts` Edge Function crashes with: `{"error":"Buffer is not defined"}`

## Solution

Replace the Edge Function code with the fixed Deno-compatible version.

---

## Option 1: Via Supabase Dashboard (Easiest)

1. **Go to Edge Functions**
   - Open Supabase Dashboard: https://supabase.com/dashboard/project/your-project-ref
   - Navigate to: Edge Functions → `generate-agent-jwts`

2. **Edit the Function**
   - Click "Edit" or "Deploy"
   - Replace ALL code with the contents of `scripts/supabase-edge-function-fixed.ts`
   - Click "Deploy"

3. **Set Environment Variables** (if not already set)
   - Go to: Settings → Edge Functions → Environment Variables
   - Add: `JWT_SECRET` = (get from Settings → API → JWT Settings → JWT Secret)
   - Add: `SUPABASE_URL` = `https://your-project.supabase.co`
   - Add: `SUPABASE_SERVICE_ROLE_KEY` = (your service_role key from .env)

4. **Test It**
   Run in PowerShell:

   ```powershell
   python -c "import requests; import os; from dotenv import load_dotenv; load_dotenv(); key = os.getenv('SUPABASE_SERVICE_ROLE_KEY'); url = os.getenv('SUPABASE_URL'); resp = requests.post(f'{url}/functions/v1/generate-agent-jwts', headers={'Authorization': f'Bearer {key}', 'apikey': key, 'Content-Type': 'application/json'}, json={}); print('Status:', resp.status_code); import json; data = resp.json(); print('Tokens:', json.dumps(data, indent=2))"
   ```

   Expected output:

   ```json
   Status: 200
   Tokens: {
     "tokens": {
          "rag-agent-service": "<JWT_REDACTED>",
          "persistence-agent-service": "<JWT_REDACTED>"
     }
   }
   ```

---

## Option 2: Contact Supabase Support

Send them this message:

> **Subject:** Edge Function `generate-agent-jwts` failing with "Buffer is not defined"
>
> **Issue:** The Edge Function crashes because it uses Node.js `Buffer` which isn't available in Deno runtime.
>
> **Error:** `{"error":"Buffer is not defined"}`
>
> **Fix:** Please replace the function code with the Deno-compatible version in the attached file `supabase-edge-function-fixed.ts`
>
> **Environment Variables Needed:**
>
> - `JWT_SECRET` (from Settings → API → JWT Secret)
> - `SUPABASE_URL`
> - `SUPABASE_SERVICE_ROLE_KEY`

---

## Option 3: Use Service Role Bypass (Current Working Solution)

If fixing the Edge Function is too much trouble, just:

1. **Run the SQL in Supabase:**
   - Open: Supabase Dashboard → SQL Editor
   - Paste: Entire `scripts/setup_rls_policies.sql` file
   - Click: Run

2. **Your agents work immediately** with `SUPABASE_KEY` (service_role)
   - RAG Agent: Uses `SUPABASE_KEY` (full access via bypass policy)
   - Persistence Agent: Uses `SUPABASE_KEY` (full access via bypass policy)

3. **Custom JWT tokens become optional** for future fine-grained permissions

---

## What to Do Now

**Recommended:** Use Option 3 (SQL bypass) to unblock yourself immediately, then fix the Edge Function later when you have time.

**Steps:**

1. Copy all of `scripts/setup_rls_policies.sql`
2. Paste into Supabase SQL Editor
3. Click "Run"
4. Test: `python -m tiers.tier_3.persistence_agent.tests.direct_test`

✅ Done!
