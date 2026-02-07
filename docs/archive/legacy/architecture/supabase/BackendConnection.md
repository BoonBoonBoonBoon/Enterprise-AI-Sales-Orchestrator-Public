Optimizing tool selection...## Simple Guide: How Agents Connect to Supabase

### The Problem We're Solving

Your agents (RAG, Persistence) need to talk to your Supabase database. But you need:
1. **Security** - Not everyone should access your database
2. **Permissions** - RAG should only READ, Persistence should WRITE
3. **Auditing** - Know who did what

---

### The Analogy: Hotel Key Cards

Think of Supabase as a **hotel** with rooms (your database tables).

| Concept | Hotel Analogy |
|---------|---------------|
| **Supabase** | The hotel building |
| **Tables** (leads, messages, etc.) | Rooms in the hotel |
| **JWT Token** | A key card |
| **Role** (reader/writer) | Key card permissions (guest vs staff) |
| **Edge Function** | The front desk that issues key cards |

---

### How It Works (Step by Step)

```
┌──────────────────────────────────────────────────────────────┐
│  STEP 1: Get a Key Card (JWT Token)                         │
│                                                              │
│  ┌─────────────┐         ┌─────────────┐                    │
│  │   You       │ ──────▶ │ Edge Func   │                    │
│  │ (Developer) │ "I need │ (Front Desk)│                    │
│  │             │  tokens"│             │                    │
│  └─────────────┘         └──────┬──────┘                    │
│                                 │                            │
│                                 ▼                            │
│                    ┌────────────────────────┐               │
│                    │ Returns 2 JWT tokens:  │               │
│                    │ • RAG token (reader)   │               │
│                    │ • Persist token (write)│               │
│                    └────────────────────────┘               │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│  STEP 2: Store the Key Cards                                │
│                                                              │
│  You save the tokens in your .env file:                     │
│                                                              │
│  SUPABASE_RAG_JWT=eyJhbG...     (reader key card)           │
│  SUPABASE_PERSISTENCE_JWT=eyJhbG...  (writer key card)      │
│                                                              │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│  STEP 3: Agent Uses Key Card to Enter                       │
│                                                              │
│  ┌─────────────┐    JWT Token     ┌─────────────┐           │
│  │ RAG Agent   │ ───────────────▶ │  Supabase   │           │
│  │             │  "Let me read"   │  Database   │           │
│  └─────────────┘                  └──────┬──────┘           │
│                                          │                   │
│                               ┌──────────▼──────────┐       │
│                               │ Supabase checks:    │       │
│                               │ • Is token valid? ✓ │       │
│                               │ • Role = reader? ✓  │       │
│                               │ • Can SELECT? ✓     │       │
│                               │ → ACCESS GRANTED    │       │
│                               └─────────────────────┘       │
└──────────────────────────────────────────────────────────────┘
```

---

### What is a JWT Token?

A JWT is just a **signed string** with information inside:

```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJyYWctYWdlbnQiLCJyb2xlIjoicmVhZGVyIn0.signature
└──────── Header ────────┘ └────────── Payload ──────────┘ └─ Signature ─┘
```

**Decoded payload:**
```json
{
  "sub": "rag-agent-service",    // Who is this?
  "user_role": "agent_reader",   // What can they do?
  "iat": 1733011200              // When was this issued?
}
```

The **signature** proves the token wasn't tampered with (like a hologram on an ID card).

---

### What is an Edge Function?

An **Edge Function** is just code that runs on Supabase's servers.

**Why use it?**
- It has access to `SUPABASE_SERVICE_ROLE_KEY` (the master key)
- The master key can create new JWT tokens
- You call it once to get your agent tokens

**You already did this:**
```powershell
$response = Invoke-RestMethod -Uri "https://ekjjqcsruwltpqkbimjo.supabase.co/functions/v1/generate-agent-jwts"
```

---

### The Two Tokens You Got

| Token | Identity | Role | Can Do |
|-------|----------|------|--------|
| `rag-agent-service` | RAG Agent | `agent_reader` | SELECT (read) |
| `persistence-agent-service` | Persistence Agent | `agent_writer` | SELECT, INSERT, UPDATE, DELETE |

---

### How Agents Use the Tokens

**Before (what you had):**
```python
# Both agents used the same key
supabase = SupabaseAdapter(url, os.getenv("SUPABASE_KEY"))
```

**After (what you'll have):**
```python
# RAG Agent - READ ONLY token
supabase = SupabaseAdapter(url, os.getenv("SUPABASE_RAG_JWT"))

# Persistence Agent - WRITE token  
supabase = SupabaseAdapter(url, os.getenv("SUPABASE_PERSISTENCE_JWT"))
```

---

### The Complete Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         YOUR SYSTEM                             │
│                                                                 │
│  ┌─────────────────┐              ┌─────────────────┐          │
│  │    RAG Agent    │              │ Persistence     │          │
│  │                 │              │ Agent           │          │
│  │ Token: reader   │              │ Token: writer   │          │
│  └────────┬────────┘              └────────┬────────┘          │
│           │                                │                    │
│           │  "SELECT * FROM leads"         │ "INSERT INTO leads"│
│           │                                │                    │
│           ▼                                ▼                    │
│  ┌──────────────────────────────────────────────────────┐      │
│  │                    SUPABASE                          │      │
│  │                                                      │      │
│  │   1. Receives request with JWT token                 │      │
│  │   2. Decodes token, checks signature                 │      │
│  │   3. Reads "user_role" from token                    │      │
│  │   4. Checks RLS policies:                            │      │
│  │      - reader → can SELECT ✓                         │      │
│  │      - writer → can SELECT, INSERT, UPDATE, DELETE ✓ │      │
│  │   5. Executes query if allowed                       │      │
│  │                                                      │      │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐    │      │
│  │  │ leads   │ │messages │ │ convos  │ │staging  │    │      │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘    │      │
│  └──────────────────────────────────────────────────────┘      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

### Summary: 5 Key Points

1. **JWT Token** = A signed ID card that says "I am X and I can do Y"

2. **Edge Function** = A trusted service that creates these ID cards using the master key

3. **Two Tokens** = One for reading (RAG), one for writing (Persistence)

4. **Supabase RLS** = Rules that check "does this token have permission to do this?"

5. **Your .env** = Where you store the tokens so your agents can use them

---

### What You Need To Do Now

1. **Get the tokens** (you already called the Edge Function)
2. **Save them in .env**
3. **Update the agents** to use the correct token
4. **Add RLS policies** in Supabase (so it knows what each role can do)

Want me to help with step 2-4?