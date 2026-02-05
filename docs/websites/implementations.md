# Implementation Details

This page provides **technical implementation guidance** for major portal features. Use this as a reference when building or extending functionality.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  Browser (Next.js App)                                          │
│  - React components + server actions                            │
│  - Supabase Auth (cookies via @supabase/ssr)                    │
└───────────────────────────────┬─────────────────────────────────┘
                                │ HTTPS
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  API Gateway (FastAPI)                                          │
│  - /api/v1/* endpoints                                          │
│  - JWT validation, RBAC, tenant enforcement                     │
│  - Rate limiting, quota checks                                  │
└───────────────────────────────┬─────────────────────────────────┘
                                │
          ┌─────────────────────┼─────────────────────┐
          ▼                     ▼                     ▼
    ┌───────────┐        ┌───────────┐        ┌───────────┐
    │ Supabase  │        │  Redis    │        │ External  │
    │ Postgres  │        │ Streams   │        │ Services  │
    │ (RLS)     │        │ (Pub/Sub) │        │ (Gmail,   │
    └───────────┘        └───────────┘        │ Slack...) │
                                              └───────────┘
```

---

## Feature Implementations

### 1. Realtime Statistics Dashboard

**Goal:** Show live metrics (emails sent, drafts pending, etc.) that update without page refresh.

**Implementation:**

```typescript
// Frontend: Subscribe to realtime updates via Supabase Realtime
import { createClient } from "@/lib/supabase/client";

const supabase = createClient();

// Subscribe to tenant's metrics channel
const channel = supabase
  .channel(`metrics:${tenantId}`)
  .on("broadcast", { event: "stats_update" }, (payload) => {
    setStats(payload.data);
  })
  .subscribe();

// Cleanup on unmount
return () => supabase.removeChannel(channel);
```

**Backend flow:**

1. Agent publishes stats update → Redis stream
2. Gateway reads stream → broadcasts to Supabase Realtime channel
3. Frontend receives broadcast → updates UI

**Database schema:**

```sql
CREATE TABLE tenant_metrics (
  tenant_id UUID REFERENCES clients(id),
  metric_key TEXT NOT NULL,
  metric_value BIGINT DEFAULT 0,
  updated_at TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (tenant_id, metric_key)
);

-- RLS: tenants see only their own metrics
ALTER TABLE tenant_metrics ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_metrics_policy ON tenant_metrics
  FOR ALL USING (tenant_id = current_setting('request.jwt.claims')::json->>'tenant_id');
```

---

### 2. A/B Testing Framework

**Goal:** Run experiments on email templates, subject lines, and strategies with statistical tracking.

**Implementation:**

**Experiment definition (DB):**

```sql
CREATE TABLE experiments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID REFERENCES clients(id),
  name TEXT NOT NULL,
  status TEXT DEFAULT 'draft', -- draft, running, paused, completed
  traffic_split JSONB NOT NULL, -- {"control": 50, "variant_a": 50}
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE experiment_variants (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  experiment_id UUID REFERENCES experiments(id),
  name TEXT NOT NULL, -- "control", "variant_a", etc.
  template_id UUID REFERENCES templates(id),
  weight INT DEFAULT 50
);

CREATE TABLE experiment_assignments (
  lead_id UUID REFERENCES leads(id),
  experiment_id UUID REFERENCES experiments(id),
  variant_id UUID REFERENCES experiment_variants(id),
  assigned_at TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (lead_id, experiment_id)
);

CREATE TABLE experiment_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  assignment_id UUID,
  event_type TEXT NOT NULL, -- "sent", "opened", "replied", "meeting_booked"
  occurred_at TIMESTAMPTZ DEFAULT now()
);
```

**Assignment logic (Python):**

```python
import random

def assign_variant(lead_id: str, experiment_id: str) -> str:
    """Assign a lead to an experiment variant (deterministic by lead_id)."""
    # Check existing assignment
    existing = get_assignment(lead_id, experiment_id)
    if existing:
        return existing.variant_id

    # Get experiment variants with weights
    variants = get_variants(experiment_id)
    total_weight = sum(v.weight for v in variants)

    # Deterministic assignment based on lead_id hash
    hash_value = int(hashlib.md5(f"{lead_id}:{experiment_id}".encode()).hexdigest(), 16)
    roll = hash_value % total_weight

    cumulative = 0
    for variant in variants:
        cumulative += variant.weight
        if roll < cumulative:
            save_assignment(lead_id, experiment_id, variant.id)
            return variant.id
```

**Statistical significance (simplified):**

```python
from scipy import stats

def calculate_significance(control_conversions, control_total,
                           variant_conversions, variant_total):
    """Two-proportion z-test for conversion rate comparison."""
    p1 = control_conversions / control_total if control_total > 0 else 0
    p2 = variant_conversions / variant_total if variant_total > 0 else 0

    # Pooled proportion
    p_pool = (control_conversions + variant_conversions) / (control_total + variant_total)

    # Standard error
    se = math.sqrt(p_pool * (1 - p_pool) * (1/control_total + 1/variant_total))

    if se == 0:
        return {"z_score": 0, "p_value": 1, "significant": False}

    z = (p2 - p1) / se
    p_value = 2 * (1 - stats.norm.cdf(abs(z)))

    return {
        "z_score": z,
        "p_value": p_value,
        "significant": p_value < 0.05,
        "lift": (p2 - p1) / p1 if p1 > 0 else 0
    }
```

---

### 3. Booking Integration

**Goal:** Let leads book meetings directly from emails.

**Implementation:**

**Calendar availability (Google Calendar):**

```python
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

def get_available_slots(user_id: str, days_ahead: int = 7) -> list[dict]:
    """Fetch available time slots from Google Calendar."""
    creds = get_user_google_credentials(user_id)
    service = build('calendar', 'v3', credentials=creds)

    now = datetime.utcnow()
    end = now + timedelta(days=days_ahead)

    # Get busy times
    body = {
        "timeMin": now.isoformat() + 'Z',
        "timeMax": end.isoformat() + 'Z',
        "items": [{"id": "primary"}]
    }

    busy_result = service.freebusy().query(body=body).execute()
    busy_times = busy_result['calendars']['primary']['busy']

    # Generate available slots (30-min increments, 9am-5pm)
    slots = []
    for day_offset in range(days_ahead):
        day = now.date() + timedelta(days=day_offset)
        for hour in range(9, 17):
            for minute in [0, 30]:
                slot_start = datetime.combine(day, time(hour, minute))
                slot_end = slot_start + timedelta(minutes=30)

                if not is_busy(slot_start, slot_end, busy_times):
                    slots.append({
                        "start": slot_start.isoformat(),
                        "end": slot_end.isoformat()
                    })

    return slots
```

**Booking confirmation:**

```sql
CREATE TABLE bookings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID REFERENCES clients(id),
  lead_id UUID REFERENCES leads(id),
  user_id UUID, -- the team member being booked
  scheduled_at TIMESTAMPTZ NOT NULL,
  duration_minutes INT DEFAULT 30,
  status TEXT DEFAULT 'confirmed', -- confirmed, cancelled, completed, no_show
  calendar_event_id TEXT, -- external calendar event ID
  created_at TIMESTAMPTZ DEFAULT now()
);
```

---

### 4. Re-Engagement Sequences

**Goal:** Automated follow-ups for non-responsive leads.

**Sequence definition:**

```sql
CREATE TABLE sequences (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID REFERENCES clients(id),
  name TEXT NOT NULL,
  status TEXT DEFAULT 'active', -- active, paused, archived
  trigger_condition JSONB NOT NULL, -- {"no_reply_days": 3}
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE sequence_steps (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  sequence_id UUID REFERENCES sequences(id),
  step_order INT NOT NULL,
  delay_hours INT DEFAULT 24,
  template_id UUID REFERENCES templates(id),
  action_type TEXT DEFAULT 'send_email' -- send_email, send_sms, notify_slack
);

CREATE TABLE sequence_enrollments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  sequence_id UUID REFERENCES sequences(id),
  lead_id UUID REFERENCES leads(id),
  current_step INT DEFAULT 0,
  status TEXT DEFAULT 'active', -- active, paused, completed, exited
  next_action_at TIMESTAMPTZ,
  enrolled_at TIMESTAMPTZ DEFAULT now()
);
```

**Sequence processor (runs on schedule):**

```python
async def process_sequences():
    """Process due sequence steps."""
    due_enrollments = await get_due_enrollments()

    for enrollment in due_enrollments:
        step = get_step(enrollment.sequence_id, enrollment.current_step)

        # Check exit conditions (e.g., lead replied)
        if await should_exit(enrollment):
            await update_enrollment_status(enrollment.id, 'exited')
            continue

        # Execute step action
        if step.action_type == 'send_email':
            await send_sequence_email(enrollment.lead_id, step.template_id)
        elif step.action_type == 'notify_slack':
            await notify_slack(enrollment)

        # Advance to next step or complete
        next_step = get_step(enrollment.sequence_id, enrollment.current_step + 1)
        if next_step:
            await advance_enrollment(enrollment.id, next_step)
        else:
            await update_enrollment_status(enrollment.id, 'completed')
```

---

### 5. CRM Integration (Salesforce Example)

**Goal:** Bi-directional sync with external CRMs.

**OAuth flow:**

```python
# Salesforce OAuth callback handler
@router.get("/integrations/salesforce/callback")
async def salesforce_callback(code: str, state: str, tenant_id: str):
    # Exchange code for tokens
    token_response = requests.post(
        "https://login.salesforce.com/services/oauth2/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": SALESFORCE_CLIENT_ID,
            "client_secret": SALESFORCE_CLIENT_SECRET,
            "redirect_uri": SALESFORCE_REDIRECT_URI
        }
    )
    tokens = token_response.json()

    # Store tokens securely
    await save_integration_tokens(
        tenant_id=tenant_id,
        integration="salesforce",
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        instance_url=tokens["instance_url"]
    )

    return RedirectResponse("/settings/integrations?success=salesforce")
```

**Sync logic:**

```python
async def sync_lead_to_salesforce(lead: Lead, tenant_id: str):
    """Push lead to Salesforce."""
    creds = await get_integration_tokens(tenant_id, "salesforce")

    sf_lead = {
        "FirstName": lead.first_name,
        "LastName": lead.last_name,
        "Email": lead.email,
        "Company": lead.company,
        "LeadSource": "Agentic System",
        "Description": f"Imported from Agentic. ID: {lead.id}"
    }

    response = requests.post(
        f"{creds.instance_url}/services/data/v58.0/sobjects/Lead/",
        headers={"Authorization": f"Bearer {creds.access_token}"},
        json=sf_lead
    )

    if response.status_code == 201:
        sf_id = response.json()["id"]
        await update_lead_external_id(lead.id, "salesforce", sf_id)
```

---

### 6. Slack / Teams Integration

**Slack notifications:**

```python
import httpx

async def send_slack_notification(webhook_url: str, message: dict):
    """Send notification to Slack channel."""
    async with httpx.AsyncClient() as client:
        await client.post(webhook_url, json={
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*New draft awaiting approval*\n{message['subject']}"
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Approve"},
                            "style": "primary",
                            "action_id": f"approve_{message['draft_id']}"
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Reject"},
                            "style": "danger",
                            "action_id": f"reject_{message['draft_id']}"
                        }
                    ]
                }
            ]
        })
```

**Slack interaction handler:**

```python
@router.post("/webhooks/slack/interactions")
async def handle_slack_interaction(request: Request):
    payload = json.loads((await request.form())["payload"])
    action = payload["actions"][0]

    if action["action_id"].startswith("approve_"):
        draft_id = action["action_id"].replace("approve_", "")
        await approve_draft(draft_id, approved_by="slack")
        return {"response_type": "ephemeral", "text": "✅ Draft approved!"}

    elif action["action_id"].startswith("reject_"):
        draft_id = action["action_id"].replace("reject_", "")
        await reject_draft(draft_id, rejected_by="slack")
        return {"response_type": "ephemeral", "text": "❌ Draft rejected."}
```

---

### 7. Database Visuals

**Lead table with filtering (React):**

```tsx
// LeadTable.tsx
import { useQuery } from "@tanstack/react-query";

export function LeadTable({ filters }: { filters: LeadFilters }) {
  const { data: leads, isLoading } = useQuery({
    queryKey: ["leads", filters],
    queryFn: () => fetchLeads(filters),
  });

  const columns = [
    { key: "name", label: "Name", sortable: true },
    { key: "company", label: "Company", sortable: true },
    { key: "status", label: "Status", sortable: true },
    { key: "lastContact", label: "Last Contact", sortable: true },
    { key: "source", label: "Source", sortable: true },
  ];

  return (
    <DataTable
      columns={columns}
      data={leads}
      loading={isLoading}
      onSort={handleSort}
      onFilter={handleFilter}
      onExport={() => exportToCsv(leads)}
    />
  );
}
```

**Funnel chart (Recharts):**

```tsx
import { FunnelChart, Funnel, LabelList, Tooltip } from "recharts";

const funnelData = [
  { name: "Leads", value: 1000, fill: "#8884d8" },
  { name: "Qualified", value: 400, fill: "#83a6ed" },
  { name: "Meeting Booked", value: 100, fill: "#8dd1e1" },
  { name: "Closed Won", value: 25, fill: "#82ca9d" },
];

export function LeadFunnel() {
  return (
    <FunnelChart width={400} height={300}>
      <Tooltip />
      <Funnel dataKey="value" data={funnelData}>
        <LabelList position="right" fill="#000" dataKey="name" />
      </Funnel>
    </FunnelChart>
  );
}
```

---

## Security Considerations

| Feature              | Security Requirement                          |
| -------------------- | --------------------------------------------- |
| OAuth integrations   | Store tokens encrypted, refresh before expiry |
| Slack/Teams webhooks | Verify request signatures                     |
| Export/import        | Rate limit, audit log all exports             |
| A/B testing          | No PII in experiment names/descriptions       |
| Booking              | Validate slot availability server-side        |

---

## See Also

- [Design Philosophy](design-philosophy.md)
- [Portal Feature Roadmap](roadmap.md)
- [API Reference](../reference/index.md)
