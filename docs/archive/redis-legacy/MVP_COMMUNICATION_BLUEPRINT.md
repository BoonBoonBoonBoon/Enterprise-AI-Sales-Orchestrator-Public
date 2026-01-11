# MVP Communication Blueprint
**Date:** November 20, 2025
**Status:** Implementation Guide

## 1. Objective
This blueprint defines the **minimal viable configuration** required to launch the Agentic System with full inter-agent communication. It focuses on the "Happy Path" for Lead Generation and Outreach.

---

## 2. Required Infrastructure

### 2.1 Redis Configuration
- **Version:** Redis 6.2+ (Required for Streams)
- **Persistence:** AOF Enabled (fsync every second)
- **Memory Policy:** `noeviction` (We manage memory via Stream `MAXLEN`)

### 2.2 Stream Inventory (The "Must-Haves")
For the MVP, we only need to provision these specific streams.

| Tier | Component | Task Stream | Result Stream |
|------|-----------|-------------|---------------|
| **T1** | Manager | `{t}:manager:tasks` | `{t}:manager:results` |
| **T2** | Leads | `{t}:orch:leads:tasks` | `{t}:orch:leads:results` |
| **T2** | Outreach | `{t}:orch:outreach:tasks` | `{t}:orch:outreach:results` |
| **T3** | RAG | `{t}:agents:rag:tasks` | `{t}:agents:rag:results` |
| **T3** | Copywriter | `{t}:agents:copy:tasks` | `{t}:agents:copy:results` |
| **T3** | Persistence | `{t}:agents:persist:tasks` | `{t}:agents:persist:results` |

> **Note:** `{t}` = Tenant ID (e.g., `acme`). `orch` = `orchestrators`.

---

## 3. Consumer Group Configuration

Run this setup script (or equivalent logic) on system startup to ensure groups exist.

```bash
# Pseudo-command reference
XGROUP CREATE {t}:manager:tasks manager-workers $ MKSTREAM
XGROUP CREATE {t}:orch:leads:tasks leads-workers $ MKSTREAM
XGROUP CREATE {t}:orch:outreach:tasks outreach-workers $ MKSTREAM
XGROUP CREATE {t}:agents:rag:tasks rag-workers $ MKSTREAM
XGROUP CREATE {t}:agents:copy:tasks copy-workers $ MKSTREAM
XGROUP CREATE {t}:agents:persist:tasks persist-workers $ MKSTREAM
```

---

## 4. Code Implementation Checklist

### 4.1 `services/redis/streams.py`
- [ ] Remove static constants (`STREAM_TASKS`, etc.).
- [ ] Add `StreamKeyBuilder` class.
- [ ] Add `ConsumerConfig` dataclass for standardized group names.

### 4.2 `core/envelope/typed_envelope.py`
- [ ] Verify `correlation_id` is mandatory in `Metadata`.
- [ ] Ensure `parent_id` field exists in `Metadata` (for tracing).

### 4.3 Consumers (`tier_*/.../consumer.py`)
- [ ] Update `__init__` to accept `tenant_id` and build stream names dynamically.
- [ ] Ensure `process_task` wraps logic in `try/except` and publishes to `:results`.
- [ ] Ensure `XACK` is called only after successful processing.

---

## 5. Deployment & Scaling Guide

### 5.1 Docker Compose (Dev)
For local development, run 1 instance of each.
```yaml
services:
  manager:
    replicas: 1
  leads_orchestrator:
    replicas: 1
  rag_agent:
    replicas: 1
```

### 5.2 Production (Kubernetes/Swarm)
Scale based on bottleneck analysis.
- **Manager:** 2 Replicas (High availability)
- **Orchestrators:** 2 Replicas
- **RAG Agent:** 4+ Replicas (CPU intensive)
- **Copywriter:** 2+ Replicas (LLM latency)
- **Persistence:** 1-2 Replicas (IO bound, database locks)

### 5.3 Monitoring
Use the following Redis commands to check health:

**Check Queue Depth (Lag):**
`XPENDING {stream} {group}`

**Check Active Consumers:**
`XINFO CONSUMERS {stream} {group}`

**Check Stream Length:**
`XLEN {stream}`
