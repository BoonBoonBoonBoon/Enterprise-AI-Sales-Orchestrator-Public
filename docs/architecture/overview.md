# Architecture Documentation

Complete architecture overview of the Agentic System, including system diagrams, data flow, deployment topology, and component interactions.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [High-Level Architecture](#high-level-architecture)
3. [Component Details](#component-details)
4. [Data Flow](#data-flow)
5. [Deployment Topology](#deployment-topology)
6. [Scaling Strategy](#scaling-strategy)
7. [Security Architecture](#security-architecture)

---

## System Overview

The Agentic System is a distributed, event-driven platform for automated marketing workflows. It uses Redis Streams for message passing, PostgreSQL (via Supabase) for persistence, and specialized agents for RAG, copywriting, and data persistence.

### Key Characteristics

- **Event-Driven**: Async message passing via Redis Streams
- **Type-Safe**: Pydantic schemas for all payloads
- **Observable**: OpenTelemetry tracing, structured logging, health endpoints
- **Resilient**: Graceful shutdown, DLQ, retry logic, circuit breakers
- **Scalable**: Horizontal worker scaling, consumer groups

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          AGENTIC SYSTEM                                 │
└─────────────────────────────────────────────────────────────────────────┘

┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│   External   │         │     API      │         │   Admin      │
│   Clients    │────────▶│   Gateway    │◀────────│   Dashboard  │
│ (TypeScript) │         │   (Future)   │         │   (Future)   │
└──────────────┘         └──────────────┘         └──────────────┘
                                │
                                │ HTTP/WebSocket
                                ▼
                         ┌──────────────┐
                         │              │
                         │ Orchestrator │
                         │   Service    │
                         │              │
                         └──────────────┘
                                │
                    ┌───────────┼───────────┐
                    │           │           │
                    ▼           ▼           ▼
            ┌───────────┐ ┌───────────┐ ┌───────────┐
            │   Redis   │ │   Redis   │ │   Redis   │
            │  Stream   │ │  Stream   │ │  Stream   │
            │ rag:tasks │ │copy:tasks │ │pers:tasks │
            └───────────┘ └───────────┘ └───────────┘
                    │           │           │
                    ▼           ▼           ▼
            ┌───────────┐ ┌───────────┐ ┌───────────┐
            │    RAG    │ │ Copywriter│ │Persistence│
            │  Workers  │ │  Workers  │ │  Workers  │
            │   (N)     │ │   (M)     │ │   (P)     │
            └───────────┘ └───────────┘ └───────────┘
                    │           │           │
                    └───────────┼───────────┘
                                │
                    ┌───────────┼───────────┐
                    ▼           ▼           ▼
            ┌───────────┐ ┌───────────┐ ┌───────────┐
            │ Supabase  │ │   Redis   │ │   Redis   │
            │ Postgres  │ │   Cache   │ │   Pub/Sub │
            │           │ │           │ │           │
            └───────────┘ └───────────┘ └───────────┘
                    │
                    ▼
            ┌───────────────────────────┐
            │  Observability Stack      │
            ├───────────────────────────┤
            │ • Jaeger (Tracing)        │
            │ • Prometheus (Metrics)    │
            │ • Grafana (Dashboards)    │
            │ • ELK Stack (Logs)        │
            └───────────────────────────┘
```

---

## Component Details

### 1. Orchestrator Service

**Purpose:** Coordinates multi-agent workflows, manages task routing, and monitors system health.

**Responsibilities:**

- Receive workflow requests from clients
- Create task envelopes with metadata
- Route tasks to appropriate agent streams
- Track workflow progress across agents
- Handle retries and DLQ management

**Tech Stack:**

- Python 3.11+
- FastAPI (HTTP API - future)
- Redis Streams (task distribution)
- Pydantic (validation)

**Streams:**

- Produces: `rag:tasks`, `copywriter:tasks`, `persistence:tasks`
- Consumes: `rag:results`, `copywriter:results`, `persistence:results`

---

### 2. RAG Agent Workers

**Purpose:** Retrieve relevant records from the database based on query specifications.

**Responsibilities:**

- Parse QuerySpec from task payload
- Execute database queries via Supabase client
- Apply filters, pagination, ordering
- Track record provenance (row hash, timestamp)
- Forward results to copywriter if specified

**Tech Stack:**

- Python 3.11+
- Supabase client (PostgreSQL)
- Redis Streams (messaging)
- OpenTelemetry (tracing)

**Streams:**

- Consumes: `rag:tasks`
- Produces: `rag:results`, `copywriter:tasks` (when forwarding)

**Configuration:**

```python
{
  "stream_name": "rag:tasks",
  "consumer_group": "rag_workers",
  "max_retries": 3,
  "timeout_ms": 30000,
  "batch_size": 10
}
```

---

### 3. Copywriter Agent Workers

**Purpose:** Generate personalized marketing copy using LLM APIs (OpenAI, Anthropic).

**Responsibilities:**

- Parse LeadData, CampaignContext, CopyInstructions
- Construct LLM prompts with personalization
- Call LLM APIs (GPT-4, Claude-3)
- Validate generated copy (length, tone)
- Calculate quality scores
- Forward to persistence for storage

**Tech Stack:**

- Python 3.11+
- LangChain (LLM abstraction)
- OpenAI/Anthropic SDKs
- Redis Streams (messaging)

**Streams:**

- Consumes: `copywriter:tasks`
- Produces: `copywriter:results`, `persistence:tasks` (when forwarding)

**Configuration:**

```python
{
  "stream_name": "copywriter:tasks",
  "consumer_group": "copywriter_workers",
  "max_retries": 3,
  "timeout_ms": 60000,
  "llm_model": "gpt-4",
  "temperature": 0.7
}
```

---

### 4. Persistence Agent Workers

**Purpose:** Write data to the database with transactional guarantees.

**Responsibilities:**

- Parse WriteSpec from task payload
- Validate data against ValidationRules
- Execute INSERT/UPDATE/UPSERT/DELETE operations
- Handle conflicts (duplicate keys, foreign keys)
- Track rows affected, conflicts resolved
- Support dry-run mode for testing

**Tech Stack:**

- Python 3.11+
- Supabase client (PostgreSQL)
- Redis Streams (messaging)

**Streams:**

- Consumes: `persistence:tasks`
- Produces: `persistence:results`

**Configuration:**

```python
{
  "stream_name": "persistence:tasks",
  "consumer_group": "persistence_workers",
  "max_retries": 2,
  "timeout_ms": 30000,
  "use_transactions": True
}
```

---

### 5. Health Server

**Purpose:** Expose health check and metrics endpoints for monitoring.

**Endpoints:**

- `GET /health` - Overall system health
- `GET /healthz` - Kubernetes liveness probe
- `GET /ready` - Kubernetes readiness probe
- `GET /metrics` - Prometheus metrics

**Metrics Exposed:**

- Stream lengths (by stream)
- Consumer lag (by consumer group)
- DLQ sizes
- Worker heartbeats
- Task throughput
- Error rates

**Tech Stack:**

- Python 3.11+
- FastAPI
- Prometheus client
- Redis (metrics source)

---

### 6. Redis Streams

**Purpose:** Distributed message queue with consumer groups and persistence.

**Streams:**

| Stream                | Purpose           | Producers                        | Consumers           |
| --------------------- | ----------------- | -------------------------------- | ------------------- |
| `rag:tasks`           | RAG queries       | Orchestrator                     | RAG Workers         |
| `rag:results`         | RAG results       | RAG Workers                      | Orchestrator        |
| `rag:dlq`             | Failed RAG tasks  | RAG Workers                      | Ops CLI             |
| `copywriter:tasks`    | Copy generation   | Orchestrator, RAG Workers        | Copywriter Workers  |
| `copywriter:results`  | Generated copy    | Copywriter Workers               | Orchestrator        |
| `copywriter:dlq`      | Failed copy tasks | Copywriter Workers               | Ops CLI             |
| `persistence:tasks`   | Write operations  | Orchestrator, Copywriter Workers | Persistence Workers |
| `persistence:results` | Write results     | Persistence Workers              | Orchestrator        |
| `persistence:dlq`     | Failed writes     | Persistence Workers              | Ops CLI             |

**Consumer Groups:**

- `rag_workers` - RAG agent consumers
- `copywriter_workers` - Copywriter consumers
- `persistence_workers` - Persistence consumers

**Configuration:**

```python
{
  "host": "localhost",
  "port": 6379,
  "db": 0,
  "namespace": "agency",
  "maxlen": 100000,  # Stream max length
  "pool_size": 10
}
```

---

### 7. Supabase (PostgreSQL)

**Purpose:** Primary data store for leads, campaigns, generated copy, and audit logs.

**Tables:**

| Table               | Purpose             | Key Columns                                         |
| ------------------- | ------------------- | --------------------------------------------------- |
| `leads`             | Lead data           | id, email, name, company, status, created_at        |
| `campaigns`         | Campaign metadata   | id, name, variant, product_name, status             |
| `generated_copy`    | Copy outputs        | id, lead_id, campaign_id, subject, body, created_at |
| `copy_metrics`      | Copy performance    | id, copy_id, opens, clicks, conversions             |
| `workflow_progress` | Multi-step tracking | workflow_id, current_step, status, percent_complete |
| `audit_logs`        | System events       | id, event_type, actor, resource, timestamp          |

**Connection:**

- Via Supabase client library
- Connection pooling (10 connections per worker)
- SSL/TLS enabled

---

## Data Flow

### End-to-End Workflow: Lead → RAG → Copy → Persist

```
┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 1: Orchestrator Creates Workflow                                   │
└──────────────────────────────────────────────────────────────────────────┘

Orchestrator:
  1. Receives workflow request: { campaign_id, filters, template }
  2. Generates correlation_id = uuid.uuid4()
  3. Creates RAGTaskPayload with ForwardSpec to copywriter
  4. Wraps in Envelope with metadata (correlation_id, priority, etc.)
  5. Sends to rag:tasks stream: XADD rag:tasks * data={envelope.json}

                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 2: RAG Worker Retrieves Leads                                      │
└──────────────────────────────────────────────────────────────────────────┘

RAG Worker:
  1. Consumes from rag:tasks: XREADGROUP GROUP rag_workers worker-1
  2. Parses Envelope from message
  3. Validates RAGTaskPayload with Pydantic
  4. Constructs SQL query from QuerySpec
  5. Executes query: SELECT * FROM leads WHERE email ILIKE '%@example.com'
  6. Retrieves 50 leads
  7. For each lead:
     - Creates CopywriterTaskPayload with LeadData + CampaignContext
     - Wraps in Envelope (same correlation_id)
     - Sends to copywriter:tasks
  8. Creates RAGResultPayload with count=50, query_time_ms=45.2
  9. Sends to rag:results
  10. ACKs message: XACK rag:tasks rag_workers {message_id}

                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 3: Copywriter Worker Generates Copy                                │
└──────────────────────────────────────────────────────────────────────────┘

Copywriter Worker (per lead):
  1. Consumes from copywriter:tasks
  2. Validates CopywriterTaskPayload
  3. Constructs LLM prompt:
     - Template: "cold_email"
     - Tone: "professional"
     - Personalization: {{name}}, {{company}}, {{title}}
  4. Calls OpenAI API: chat.completions.create(model="gpt-4", ...)
  5. Receives response with subject + body
  6. Validates output (min length, no profanity)
  7. Creates PersistenceTaskPayload:
     - WriteSpec: table=generated_copy, operation=INSERT
     - Data: { lead_id, campaign_id, subject, body }
  8. Wraps in Envelope (same correlation_id)
  9. Sends to persistence:tasks
  10. Creates CopywriterResultPayload
  11. Sends to copywriter:results
  12. ACKs message

                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 4: Persistence Worker Saves Copy                                   │
└──────────────────────────────────────────────────────────────────────────┘

Persistence Worker:
  1. Consumes from persistence:tasks
  2. Validates PersistenceTaskPayload
  3. Runs ValidationRules (e.g., lead_id required)
  4. Begins transaction
  5. Executes INSERT:
     INSERT INTO generated_copy (lead_id, campaign_id, subject, body)
     VALUES ('lead-123', 'camp-456', 'Subject...', 'Body...')
  6. Commits transaction
  7. Creates PersistenceResultPayload (rows_affected=1)
  8. Sends to persistence:results
  9. ACKs message

                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 5: Orchestrator Tracks Completion                                  │
└──────────────────────────────────────────────────────────────────────────┘

Orchestrator:
  1. Consumes from rag:results, copywriter:results, persistence:results
  2. Matches by correlation_id
  3. Updates workflow_progress table:
     - workflow_id = correlation_id
     - steps_completed = ["rag", "copywriter", "persistence"]
     - status = "completed"
     - percent_complete = 100
  4. Logs completion event
  5. Returns response to client (if synchronous API)
```

### Distributed Tracing Flow

```
Trace Context Propagation (W3C Trace Context):

┌─────────────────────────────────────────────────────────────────┐
│ Orchestrator (trace_id: abc123, span_id: span-001)             │
└─────────────────────────────────────────────────────────────────┘
                            │
                            │ Envelope metadata.tags["traceparent"]
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ RAG Worker (trace_id: abc123, span_id: span-002, parent: 001)  │
└─────────────────────────────────────────────────────────────────┘
                            │
                            │ Envelope metadata.tags["traceparent"]
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ Copywriter (trace_id: abc123, span_id: span-003, parent: 002)  │
└─────────────────────────────────────────────────────────────────┘
                            │
                            │ Envelope metadata.tags["traceparent"]
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ Persistence (trace_id: abc123, span_id: span-004, parent: 003) │
└─────────────────────────────────────────────────────────────────┘

All spans exported to Jaeger for visualization.
```

---

## Deployment Topology

### Development (Local Docker Compose)

```yaml
services:
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    volumes: ["redis_data:/data"]

  postgres:
    image: postgres:15-alpine
    ports: ["5432:5432"]
    environment:
      POSTGRES_DB: agency
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: secret

  orchestrator:
    build: .
    command: python -m agent.orchestrator.main
    environment:
      REDIS_HOST: redis
      DATABASE_URL: postgresql://admin:secret@postgres:5432/agency

  rag_worker:
    build: .
    command: python -m agent.operational_agents.rag_agent.worker
    environment:
      REDIS_HOST: redis
      DATABASE_URL: postgresql://admin:secret@postgres:5432/agency
    deploy:
      replicas: 2

  copywriter_worker:
    build: .
    command: python -m agent.operational_agents.copywriter.worker
    environment:
      REDIS_HOST: redis
      OPENAI_API_KEY: ${OPENAI_API_KEY}
    deploy:
      replicas: 3

  persistence_worker:
    build: .
    command: python -m agent.operational_agents.persistence_agent.write_worker
    environment:
      REDIS_HOST: redis
      DATABASE_URL: postgresql://admin:secret@postgres:5432/agency
    deploy:
      replicas: 2

  health_server:
    build: .
    command: python scripts/health_server.py
    ports: ["8000:8000"]
    environment:
      REDIS_HOST: redis

  jaeger:
    image: jaegertracing/all-in-one:latest
    ports: ["16686:16686", "4318:4318"]
```

**Access Points:**

- Health Server: http://localhost:8000/health
- Jaeger UI: http://localhost:16686
- Redis: localhost:6379
- PostgreSQL: localhost:5432

---

### Production (Kubernetes)

```yaml
# Simplified K8s deployment structure

apiVersion: apps/v1
kind: Deployment
metadata:
  name: orchestrator
spec:
  replicas: 2
  selector:
    matchLabels:
      app: orchestrator
  template:
    metadata:
      labels:
        app: orchestrator
    spec:
      containers:
      - name: orchestrator
        image: agency/orchestrator:v1.0.0
        env:
        - name: REDIS_HOST
          valueFrom:
            secretKeyRef:
              name: redis-credentials
              key: host
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"

---

apiVersion: apps/v1
kind: Deployment
metadata:
  name: rag-worker
spec:
  replicas: 5  # Scale based on rag:tasks stream length
  ...

---

apiVersion: apps/v1
kind: Deployment
metadata:
  name: copywriter-worker
spec:
  replicas: 10  # Higher replicas for LLM-heavy workload
  ...

---

apiVersion: v1
kind: Service
metadata:
  name: health-server
spec:
  selector:
    app: health-server
  ports:
  - port: 8000
    targetPort: 8000
  type: LoadBalancer

---

# Horizontal Pod Autoscaler for workers
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: rag-worker-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: rag-worker
  minReplicas: 2
  maxReplicas: 20
  metrics:
  - type: External
    external:
      metric:
        name: redis_stream_length
        selector:
          matchLabels:
            stream: "agency:rag:tasks"
      target:
        type: AverageValue
        averageValue: "100"  # Scale up if >100 pending tasks
```

**Infrastructure Components:**

- **Redis:** Managed Redis (AWS ElastiCache, Azure Cache for Redis, GCP Memorystore)
- **PostgreSQL:** Supabase hosted or managed PostgreSQL (RDS, Cloud SQL)
- **Observability:** Datadog, New Relic, or self-hosted Prometheus + Grafana + Jaeger
- **Secrets:** Azure Key Vault, AWS Secrets Manager, GCP Secret Manager
- **Load Balancer:** Cloud provider load balancer for health server

---

## Scaling Strategy

### Horizontal Scaling

| Component           | Scaling Trigger                 | Min | Max | Notes                       |
| ------------------- | ------------------------------- | --- | --- | --------------------------- |
| Orchestrator        | CPU >70%                        | 2   | 10  | Stateless, can scale freely |
| RAG Workers         | `rag:tasks` length >100         | 2   | 20  | Scale with query volume     |
| Copywriter Workers  | `copywriter:tasks` length >50   | 3   | 30  | LLM API rate limits apply   |
| Persistence Workers | `persistence:tasks` length >100 | 2   | 15  | DB connection pool limits   |

### Vertical Scaling

| Component           | CPU      | Memory | Notes                    |
| ------------------- | -------- | ------ | ------------------------ |
| Orchestrator        | 1-2 vCPU | 1-2 GB | Lightweight coordination |
| RAG Workers         | 1 vCPU   | 1 GB   | Database client overhead |
| Copywriter Workers  | 2 vCPU   | 2 GB   | LLM API client + caching |
| Persistence Workers | 1 vCPU   | 1 GB   | Database client overhead |

### Autoscaling Configuration

```yaml
# Kubernetes HPA example for RAG workers
metrics:
  - type: External
    external:
      metric:
        name: redis_stream_length
        selector:
          matchLabels:
            stream: "agency:rag:tasks"
      target:
        type: AverageValue
        averageValue: "100" # Target: 100 pending tasks per pod

  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70

behavior:
  scaleUp:
    stabilizationWindowSeconds: 60
    policies:
      - type: Percent
        value: 50 # Scale up by 50% at a time
        periodSeconds: 60

  scaleDown:
    stabilizationWindowSeconds: 300
    policies:
      - type: Pods
        value: 1 # Scale down 1 pod at a time
        periodSeconds: 120
```

---

## Security Architecture

### Network Security

```
┌─────────────────────────────────────────────────────────────────┐
│ EXTERNAL NETWORK (Internet)                                    │
└─────────────────────────────────────────────────────────────────┘
                            │
                            │ HTTPS (TLS 1.3)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ WAF / API Gateway (Rate Limiting, DDoS Protection)             │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ PRIVATE NETWORK (VPC)                                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐   │
│  │ Orchestrator │────▶│    Redis     │◀────│   Workers    │   │
│  │  (Private)   │     │  (Private)   │     │  (Private)   │   │
│  └──────────────┘     └──────────────┘     └──────────────┘   │
│                              │                                  │
│                              ▼                                  │
│                       ┌──────────────┐                         │
│                       │  Supabase    │                         │
│                       │  (Private)   │                         │
│                       └──────────────┘                         │
└─────────────────────────────────────────────────────────────────┘
```

### Authentication & Authorization

1. **Redis ACLs** (Future):

   ```
   user rag_worker on >password ~agency:rag:* &rag_workers +@read +xreadgroup +xack
   user copywriter_worker on >password ~agency:copywriter:* &copywriter_workers +@read +xreadgroup +xack
   user persistence_worker on >password ~agency:persistence:* &persistence_workers +@read +xreadgroup +xack
   ```

2. **Database Row-Level Security** (Supabase):

   ```sql
   CREATE POLICY tenant_isolation ON leads
   FOR ALL USING (tenant_id = current_setting('app.tenant_id'));
   ```

3. **Secrets Management**:
   - API keys stored in Azure Key Vault / AWS Secrets Manager
   - Injected as environment variables at runtime
   - Rotated every 90 days
   - Never committed to source control

### Data Encryption

- **In Transit:** TLS 1.3 for all network connections
- **At Rest:** AES-256 encryption for database and Redis snapshots
- **Sensitive Fields:** PII (email, name) encrypted with customer-managed keys

### Compliance

- **GDPR:** Right to erasure implemented via soft deletes + purge job
- **SOC 2:** Audit logs for all data access and modifications
- **HIPAA:** PHI fields encrypted, access logged, retention policies enforced

---

## See Also

- [API Reference](../api/reference.md) - Envelope and payload schemas
- [Type Safety Guide](../TYPE_SAFETY.md) - Pydantic validation
- [Incident Playbooks](../INCIDENT_PLAYBOOKS.md) - Operational runbooks
- [Tracing Setup](../updates/TRACING_SETUP.md) - Distributed tracing
- [Enhancements](../updates/ENHANCEMENTS.md) - System changes and ops notes

---

**Last Updated:** October 26, 2025  
**Version:** 1.0.0
