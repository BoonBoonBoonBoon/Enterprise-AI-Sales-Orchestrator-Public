# MVP Implementation Plan - SDR Automation System

**Document Version:** 1.0  
**Date:** November 29, 2025  
**Objective:** Fastest path to functional SDR automation system (Lead Discovery → Qualification → Enrichment → Outreach → Booking → AE Handoff)

---

## Executive Summary

This plan outlines a 4-week implementation roadmap to deliver a functional SDR automation system. The system will handle the complete SDR workflow: discovering leads, qualifying them, enriching with company data, executing multi-channel outreach campaigns, monitoring replies, booking meetings, and handing off to Account Executives.

**Current State:**

- ✅ Redis hierarchical architecture implemented and tested
- ✅ Manager + 2 Orchestrators + 3 Agents operational
- ✅ Database schema complete (27 fields in `leads` table)
- ⚠️ RAG enrichment returns empty (missing API keys)
- ⚠️ Copywriter agent stubbed (LLM not wired)
- ❌ Email delivery not integrated
- ❌ Inbound monitoring not implemented

**MVP Goal:** End-to-end workflow where a new lead automatically flows through discovery → enrichment → personalized outreach → meeting booked → AE notified.

---

## Phase 0: Critical Blockers (Week 0 - This Week)

**Goal:** Fix broken enrichment pipeline so RAG agent returns real company data.

### 0.1 Add External API Keys (30 minutes)

**Current Issue:** RAG agent returns `enriched_fields: ["messages"]` only, no company data.

**Root Cause:** Missing environment variables:

- `CRUNCHBASE_API_KEY` - Company data (funding, size, industry)
- `LINKEDIN_ACCESS_TOKEN` or Proxycurl key - Professional data

**Action Items:**

1. **Crunchbase Setup:**
   - Sign up at https://www.crunchbase.com/api
   - Get API key from dashboard
   - Add to `.env`: `CRUNCHBASE_API_KEY=your_key_here`

2. **LinkedIn Data (Choose One):**
   - **Option A - Proxycurl** (Recommended for MVP):
     - Sign up at https://nubela.co/proxycurl/
     - Get API key
     - Add to `.env`: `PROXYCURL_API_KEY=your_key_here`
   - **Option B - LinkedIn Official API**:
     - Requires OAuth flow and app approval
     - Add to `.env`: `LINKEDIN_ACCESS_TOKEN=your_token_here`

3. **Verify `.env` file location:**
   ```
   c:\Users\Elliot\Desktop\Agency Files\Important\Technicals\Agentic System\.env
   ```

**Files to Update:**

- `.env` - Add API keys
- `tiers/tier_3/rag_agent/rag_agent.py` - Verify API integration code (lines 150-200)

### 0.2 Wire Copywriter Agent to OpenAI (2 hours)

**Current Issue:** `_call_llm()` method stubbed, falls back to templates.

**File:** `tiers/tier_3/copywriter_agent/copywriter.py`

**Action Items:**

1. Import OpenAI SDK (already in dependencies):

   ```python
   from openai import AsyncOpenAI
   ```

2. Replace `_call_llm()` stub (around line 85):

   ```python
   async def _call_llm(self, prompt: str, model: str = "gpt-4") -> str:
       client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
       response = await client.chat.completions.create(
           model=model,
           messages=[{"role": "user", "content": prompt}],
           temperature=0.7
       )
       return response.choices[0].message.content
   ```

3. Update `generate_email_copy()` to use real LLM:
   - Pass lead data (name, company, role, pain points) to prompt
   - Use enriched data from RAG agent (company size, funding, industry)
   - Generate personalized subject line + body

**Expected Output:** Personalized emails using lead-specific data, not generic templates.

### 0.3 Restart Consumers & Test (1 hour)

**Action Items:**

1. Restart all consumers with new code:

   ```powershell
   .\restart_consumers.ps1
   ```

2. Run E2E test with enrichment verification:

   ```powershell
   python fresh_test.py
   ```

3. **Manual Verification:**
   - Check Redis browser: `agentic-dev:agents:rag:results` should have enriched data
   - Query Supabase `leads` table: Verify `raw_data` JSONB field contains company info
   - Check logs: RAG agent should log successful API calls to Crunchbase/LinkedIn

**Success Criteria:**

- ✅ RAG agent returns `enriched_fields: ["company_name", "industry", "employee_count", "funding_stage", ...]`
- ✅ Supabase `leads.raw_data` contains JSON with external API responses
- ✅ No errors in consumer logs about missing API keys

---

## Phase 1: Core Lead Pipeline (Week 1)

**Goal:** "Raw Lead → Enriched Lead" - Reliable enrichment + persistence workflow.

### 1.1 Lead Discovery Integration (8 hours)

**Current State:** No automated lead source configured.

**Options (Choose One for MVP):**

**Option A - Apollo.io** (Recommended):

- **Pros:** Large B2B database, good filters, reasonable pricing
- **Cons:** Requires paid plan for API access
- **Implementation:**
  1. Sign up at https://apollo.io
  2. Get API key from Settings
  3. Create `services/external_apis/apollo_client.py`:
     ```python
     class ApolloClient:
         async def search_leads(self, filters: dict) -> list[dict]:
             # Call Apollo API /v1/mixed_people/search
             # Return list of leads with: name, email, company, title
     ```
  4. Create scheduled task (cron/Windows Task Scheduler) to run daily:
     ```powershell
     python -m scripts.daily_lead_discovery
     ```
  5. Script delegates to Manager: "Find and qualify 50 new leads in {industry}"

**Option B - Manual CSV Upload** (Fastest MVP):

- **Pros:** No API integration needed, immediate testing
- **Cons:** Not fully automated
- **Implementation:**
  1. Export leads from Sales Navigator/ZoomInfo to CSV
  2. Create `scripts/import_leads_from_csv.py`
  3. Script inserts into `staging_leads` table
  4. Trigger Manager with "Process staging leads" task

**Option C - LinkedIn Sales Navigator Scraper**:

- **Pros:** Access to LinkedIn data directly
- **Cons:** Against ToS, account risk, requires Selenium
- **Recommendation:** Avoid for production, use Proxycurl instead

**Decision Point:** Choose lead source by end of Week 1 Day 1.

### 1.2 Qualification Logic Enhancement (4 hours)

**Current State:** RAG agent has qualification logic but needs tuning.

**File:** `tiers/tier_3/rag_agent/rag_agent.py`

**Action Items:**

1. Define qualification criteria in `config/qualification_rules.py`:

   ```python
   QUALIFICATION_RULES = {
       "company_size": {"min": 50, "max": 5000},  # Employee count
       "funding_stage": ["Series A", "Series B", "Series C", "Growth"],
       "industries": ["SaaS", "FinTech", "E-commerce", "HealthTech"],
       "exclude_titles": ["Student", "Intern", "Freelance"],
       "required_titles": ["VP", "Director", "Head of", "Chief", "Manager"]
   }
   ```

2. Update RAG agent `qualify_lead()` method:
   - Check company size against rules
   - Check funding stage (from Crunchbase)
   - Check title against required/exclude lists
   - Calculate `lead_score` (0-100) based on match quality

3. Update `leads` table via Persistence agent:
   - `qualification_status`: "qualified" | "disqualified" | "pending"
   - `lead_score`: Integer 0-100
   - `disqualification_reason`: String (if disqualified)

**Success Criteria:**

- ✅ Only leads with `lead_score >= 70` marked as "qualified"
- ✅ Disqualified leads have clear reason logged
- ✅ Qualification rules configurable without code changes

### 1.3 Deduplication Agent Creation (6 hours)

**Current State:** Mentioned in docs but not implemented.

**Why Needed:** Prevent duplicate outreach to same person/company.

**Action Items:**

1. Create `tiers/tier_3/deduplication_agent/` directory structure:

   ```
   deduplication_agent/
   ├── __init__.py
   ├── deduplication.py
   ├── consumer.py
   └── README.md
   ```

2. Implement deduplication logic (`deduplication.py`):

   ```python
   class DeduplicationAgent:
       async def check_duplicate(self, lead: dict) -> dict:
           # Query Supabase for existing leads
           # Match on: email (exact), company + title (fuzzy)
           # Return: is_duplicate, existing_lead_id, confidence_score
   ```

3. Create Redis consumer (`consumer.py`):
   - Listen on: `agentic-dev:agents:deduplication:tasks`
   - Respond to: `agentic-dev:agents:deduplication:results`

4. Update Leads orchestrator delegation tools:
   - Add `delegate_to_deduplication_agent()` tool
   - Call after RAG enrichment, before marking qualified

5. Define deduplication strategy:
   - **Email match:** 100% duplicate, skip
   - **Same company + similar title:** 90% duplicate, merge data
   - **Same person, different company:** Update company, continue

**Success Criteria:**

- ✅ No duplicate emails in `leads` table
- ✅ Deduplication agent handles 1000+ leads/hour
- ✅ Merged duplicates preserve most recent enriched data

### 1.4 End-to-End Pipeline Test (2 hours)

**Test Scenario:** CSV Upload → Staging → Enrichment → Qualification → Deduplication → Supabase

**Action Items:**

1. Create test CSV with 10 leads:
   - 5 qualified (good company size, funding, title)
   - 3 disqualified (small company, wrong title)
   - 2 duplicates (same email as existing leads)

2. Run import script:

   ```powershell
   python -m scripts.import_leads_from_csv --file test_leads.csv
   ```

3. Monitor Redis streams:
   - Manager → Leads orchestrator
   - Leads → RAG → Persistence → Deduplication

4. Verify Supabase results:
   ```sql
   SELECT email, qualification_status, lead_score, enrichment_status
   FROM leads
   WHERE created_at > NOW() - INTERVAL '1 hour';
   ```

**Expected Results:**

- 5 leads: `qualification_status = "qualified"`, `enrichment_status = "complete"`
- 3 leads: `qualification_status = "disqualified"`
- 2 leads: Skipped (duplicate detection)

---

## Phase 2: Outreach Pipeline (Week 2)

**Goal:** "Qualified Lead → First Email Sent" - Generate personalized copy + deliver emails.

### 2.1 Email Delivery Service Integration (4 hours)

**Current State:** No email sender configured.

**Options (Choose One for MVP):**

**Option A - SendGrid** (Recommended):

- **Pros:** 100 emails/day free, good deliverability, simple API
- **Cons:** Requires domain verification for production
- **Implementation:**
  1. Sign up at https://sendgrid.com
  2. Get API key
  3. Add to `.env`: `SENDGRID_API_KEY=your_key_here`
  4. Create `services/external_apis/email_sender.py`:

     ```python
     from sendgrid import SendGridAPIClient
     from sendgrid.helpers.mail import Mail

     class EmailSender:
         def send_email(self, to: str, subject: str, body: str, from_email: str):
             message = Mail(
                 from_email=from_email,
                 to_emails=to,
                 subject=subject,
                 html_content=body
             )
             sg = SendGridAPIClient(os.getenv('SENDGRID_API_KEY'))
             response = sg.send(message)
             return response.status_code
     ```

**Option B - Postmark**:

- **Pros:** Excellent deliverability, transactional focus
- **Cons:** No free tier (pay per email)

**Option C - AWS SES**:

- **Pros:** Very cheap at scale
- **Cons:** Sandbox requires approval, complex setup

**Decision Point:** Choose email service by Week 2 Day 1.

**Domain Setup (Required for Production):**

1. Add SPF record: `v=spf1 include:sendgrid.net ~all`
2. Add DKIM records (from SendGrid dashboard)
3. Add DMARC record: `v=DMARC1; p=none; rua=mailto:dmarc@yourdomain.com`
4. Verify domain in SendGrid before sending

### 2.2 Outreach Orchestrator Activation (6 hours)

**Current State:** Code exists but not tested E2E.

**File:** `tiers/tier_2/outreach_orchestrator/consumer.py`

**Action Items:**

1. Start Outreach consumer:

   ```powershell
   # Terminal 3 - Outreach Orchestrator
   $env:TENANT_ID = 'agentic-dev'
   python -m tiers.tier_2.outreach_orchestrator.consumer
   ```

2. Test Manager → Outreach delegation:

   ```python
   # In Python shell or test script
   from tiers.tier_1.manager.tools.delegation_tools import delegate_to_outreach_orchestrator

   task = {
       "action": "create_email_campaign",
       "lead_ids": [1, 2, 3],
       "campaign_type": "initial_outreach"
   }
   result = delegate_to_outreach_orchestrator(task)
   ```

3. Verify Outreach → Copywriter delegation:
   - Monitor `agentic-dev:agents:copywriter:tasks`
   - Check Copywriter agent returns personalized email

4. Wire email sending:
   - Update Outreach orchestrator to call `EmailSender.send_email()`
   - Log sent emails to `outreach_log` table (create if needed)

**Database Schema for `outreach_log` table:**

```sql
CREATE TABLE outreach_log (
  id SERIAL PRIMARY KEY,
  lead_id INTEGER REFERENCES leads(id),
  campaign_id VARCHAR(100),
  channel VARCHAR(50), -- 'email', 'linkedin', 'phone'
  subject TEXT,
  body TEXT,
  sent_at TIMESTAMP DEFAULT NOW(),
  status VARCHAR(50), -- 'sent', 'failed', 'bounced', 'opened', 'replied'
  external_message_id VARCHAR(255) -- From SendGrid
);
```

### 2.3 Multi-Channel Sequence Implementation (8 hours)

**Current State:** Outreach orchestrator has sequence logic but not fully wired.

**Workflow:** Email (Day 0) → LinkedIn (Day 3) → Phone (Day 7) → Follow-up (Day 10)

**Action Items:**

1. Create `config/outreach_sequences.py`:

   ```python
   DEFAULT_SEQUENCE = [
       {"day": 0, "channel": "email", "template": "initial_intro"},
       {"day": 3, "channel": "linkedin", "template": "connection_request"},
       {"day": 7, "channel": "phone", "template": "call_script"},
       {"day": 10, "channel": "email", "template": "follow_up"}
   ]
   ```

2. Create Sequencing Agent (or add to Outreach orchestrator):
   - **Option A - New Agent:** `tiers/tier_3/sequencing_agent/`
   - **Option B - Orchestrator Tool:** Add `schedule_next_touchpoint()` method

3. Implement scheduling mechanism:
   - **Option A - Redis Delayed Messages:** Use Redis Streams with future timestamp
   - **Option B - Cron Job:** Daily script checks `outreach_log`, schedules next touchpoint
   - **Option C - Celery Beat:** Task queue with scheduled tasks

4. LinkedIn outreach (if needed):
   - **Manual for MVP:** Generate LinkedIn message copy, SDR sends manually
   - **Automated:** Requires LinkedIn API (complex OAuth) or Phantombuster integration

5. Phone outreach:
   - **MVP Approach:** Generate call script, log "scheduled_call" in CRM
   - **Future:** Twilio integration for automated dialing

**Decision Point:** Choose scheduling mechanism by Week 2 Day 2.

### 2.4 Campaign Management (4 hours)

**Goal:** Track outreach campaigns, metrics, and performance.

**Database Schema for `campaigns` table:**

```sql
CREATE TABLE campaigns (
  id SERIAL PRIMARY KEY,
  name VARCHAR(255),
  created_at TIMESTAMP DEFAULT NOW(),
  status VARCHAR(50), -- 'active', 'paused', 'completed'
  target_industry VARCHAR(100),
  target_company_size VARCHAR(50),
  total_leads INTEGER DEFAULT 0,
  emails_sent INTEGER DEFAULT 0,
  opens INTEGER DEFAULT 0,
  replies INTEGER DEFAULT 0,
  meetings_booked INTEGER DEFAULT 0
);
```

**Action Items:**

1. Create campaign before outreach:

   ```python
   campaign = {
       "name": "Q4 SaaS Outreach",
       "target_industry": "SaaS",
       "target_company_size": "50-500"
   }
   ```

2. Link leads to campaign:
   - Add `campaign_id` column to `leads` table
   - Update on outreach start

3. Create metrics dashboard (simple for MVP):
   - Script: `scripts/campaign_metrics.py`
   - Output: Markdown report or terminal table
   ```
   Campaign: Q4 SaaS Outreach
   Total Leads: 100
   Emails Sent: 100 (100%)
   Opens: 45 (45%)
   Replies: 12 (12%)
   Meetings Booked: 5 (5%)
   ```

---

## Phase 3: Inbound Monitoring (Week 3)

**Goal:** "Reply Detection → Next Action" - Detect email replies, update lead status, trigger booking flow.

### 3.1 Email Webhook Setup (4 hours)

**Current State:** No inbound monitoring.

**Approach:** Use SendGrid/Postmark webhooks to notify when replies received.

**Action Items:**

1. Create webhook endpoint:
   - **File:** `api/webhooks/email_reply.py`
   - **Framework:** Flask or FastAPI (lightweight)

   ```python
   from fastapi import FastAPI, Request

   app = FastAPI()

   @app.post("/webhooks/sendgrid/reply")
   async def handle_email_reply(request: Request):
       data = await request.json()
       # Extract: from_email, to_email, subject, body, timestamp
       # Parse sentiment: positive, negative, neutral
       # Update lead status in Supabase
       # Trigger next action (booking flow if positive)
   ```

2. Deploy webhook endpoint:
   - **Option A - ngrok (for testing):** `ngrok http 8000`
   - **Option B - Cloud Run (GCP):** Serverless deployment
   - **Option C - Railway/Render:** Simple hosting

3. Configure SendGrid webhook:
   - Go to SendGrid > Settings > Inbound Parse
   - Add domain: `reply.yourdomain.com`
   - Forward to webhook URL: `https://your-url.com/webhooks/sendgrid/reply`

4. Test webhook:
   - Send test email to yourself
   - Reply to email
   - Check logs: Webhook should receive reply data

**Decision Point:** Choose deployment platform by Week 3 Day 1.

### 3.2 Reply Sentiment Analysis (6 hours)

**Goal:** Classify replies as positive (interested), negative (not interested), or neutral (question/objection).

**Action Items:**

1. Create `services/sentiment_analyzer.py`:

   ```python
   from openai import OpenAI

   class SentimentAnalyzer:
       def analyze_reply(self, email_body: str) -> dict:
           client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
           prompt = f"""
           Classify this email reply sentiment:
           - "positive": Interested, wants meeting/demo/more info
           - "negative": Not interested, unsubscribe, wrong person
           - "neutral": Question, objection, need more info

           Reply: {email_body}

           Return JSON: {{"sentiment": "positive|negative|neutral", "reason": "brief explanation"}}
           """
           response = client.chat.completions.create(
               model="gpt-4",
               messages=[{"role": "user", "content": prompt}]
           )
           return json.loads(response.choices[0].message.content)
   ```

2. Integrate into webhook:
   - Call `SentimentAnalyzer.analyze_reply()` in webhook handler
   - Update `leads` table: `reply_sentiment`, `last_reply_at`

3. Define next actions based on sentiment:

   ```python
   SENTIMENT_ACTIONS = {
       "positive": "trigger_booking_flow",
       "negative": "mark_as_disqualified",
       "neutral": "schedule_follow_up"
   }
   ```

4. Trigger appropriate workflow:
   - **Positive:** Delegate to Outreach → Booking Agent
   - **Negative:** Update status, remove from campaign
   - **Neutral:** Schedule follow-up email in 2 days

### 3.3 Booking Agent Creation (8 hours)

**Current State:** Mentioned in docs but not implemented.

**Goal:** Send calendar link, track booking status.

**Action Items:**

1. Create `tiers/tier_3/booking_agent/` directory structure:

   ```
   booking_agent/
   ├── __init__.py
   ├── booking.py
   ├── consumer.py
   └── README.md
   ```

2. Choose calendar integration:
   - **Option A - Calendly** (Easiest MVP):
     - Sign up at https://calendly.com
     - Get booking page URL: `https://calendly.com/your-name/30min`
     - No API needed, just include link in email
   - **Option B - Cal.com** (Open-source):
     - Self-host or use cloud version
     - API integration for booking tracking
   - **Option C - Google Calendar API**:
     - Full control, complex OAuth setup
     - Create events programmatically

3. Implement booking flow (`booking.py`):

   ```python
   class BookingAgent:
       def send_booking_link(self, lead_email: str, calendly_url: str):
           # Generate personalized booking email
           subject = "Let's schedule a quick call"
           body = f"""
           Hi {lead_name},

           Thanks for your interest! I'd love to chat about how we can help.

           Book a time that works for you: {calendly_url}

           Looking forward to it!
           """
           # Send via EmailSender

       def track_booking(self, lead_id: int, event_data: dict):
           # Update leads table: booking_status = "confirmed"
           # Log to bookings table
   ```

4. Create `bookings` table:

   ```sql
   CREATE TABLE bookings (
     id SERIAL PRIMARY KEY,
     lead_id INTEGER REFERENCES leads(id),
     scheduled_at TIMESTAMP,
     duration_minutes INTEGER,
     status VARCHAR(50), -- 'pending', 'confirmed', 'completed', 'no-show'
     meeting_notes TEXT,
     calendly_event_id VARCHAR(255)
   );
   ```

5. Calendly webhook (if using Calendly API):
   - Endpoint: `/webhooks/calendly/booking`
   - Updates `bookings` table when event scheduled/cancelled

**Decision Point:** Choose calendar tool by Week 3 Day 2.

### 3.4 Auto-Responder (Optional - 4 hours)

**Goal:** Automatically respond to common questions/objections.

**Use Cases:**

- "What's the pricing?" → Send pricing page link
- "Can you send more info?" → Send case studies PDF
- "Not the right time" → Schedule follow-up in 3 months

**Action Items:**

1. Create response templates in `config/auto_responses.py`:

   ```python
   AUTO_RESPONSES = {
       "pricing_question": {
           "triggers": ["price", "cost", "pricing", "how much"],
           "response": "Great question! Our pricing starts at $X/month. Here's a detailed breakdown: [link]"
       },
       "more_info": {
           "triggers": ["more information", "case study", "examples"],
           "response": "Absolutely! I've attached some case studies showing how we helped companies like yours."
       }
   }
   ```

2. Integrate into webhook:
   - Check reply body for trigger keywords
   - Send auto-response if match found
   - Still update lead status and notify SDR

3. Add human handoff:
   - If no auto-response match → Flag for manual review
   - Slack notification: "New reply from {lead_name}: {preview}"

---

## Phase 4: AE Handoff (Week 4)

**Goal:** "Qualified Lead → CRM" - Move meeting-booked leads to AE's workflow.

### 4.1 Define Handoff Criteria (2 hours)

**Action Items:**

1. Create `config/handoff_rules.py`:

   ```python
   HANDOFF_CRITERIA = {
       "lead_score": 80,  # Minimum qualification score
       "booking_status": "confirmed",  # Meeting scheduled
       "qualification_status": "qualified",
       "enrichment_status": "complete"
   }
   ```

2. Create handoff query:

   ```sql
   SELECT * FROM leads
   WHERE lead_score >= 80
   AND booking_status = 'confirmed'
   AND qualification_status = 'qualified'
   AND handoff_status IS NULL;
   ```

3. Schedule daily handoff check:
   ```powershell
   # Windows Task Scheduler or cron
   python -m scripts.daily_handoff_check
   ```

### 4.2 CRM Integration (6 hours)

**Current State:** No CRM integration.

**Options (Choose One for MVP):**

**Option A - HubSpot** (Recommended):

- **Pros:** Free tier, good API, popular
- **Cons:** Rate limits on free tier
- **Implementation:**
  1. Sign up at https://hubspot.com
  2. Get API key from Settings > Integrations
  3. Add to `.env`: `HUBSPOT_API_KEY=your_key_here`
  4. Create `services/external_apis/hubspot_client.py`:

     ```python
     import requests

     class HubSpotClient:
         def create_contact(self, lead: dict) -> str:
             url = "https://api.hubapi.com/crm/v3/objects/contacts"
             headers = {"Authorization": f"Bearer {os.getenv('HUBSPOT_API_KEY')}"}
             data = {
                 "properties": {
                     "email": lead["email"],
                     "firstname": lead["first_name"],
                     "lastname": lead["last_name"],
                     "company": lead["company_name"],
                     "jobtitle": lead["title"],
                     "lead_score": lead["lead_score"]
                 }
             }
             response = requests.post(url, headers=headers, json=data)
             return response.json()["id"]
     ```

**Option B - Salesforce**:

- **Pros:** Enterprise standard, powerful
- **Cons:** Expensive, complex setup

**Option C - Pipedrive**:

- **Pros:** Simple, sales-focused
- **Cons:** Less integrations than HubSpot

**Decision Point:** Choose CRM by Week 4 Day 1.

### 4.3 Handoff Workflow (6 hours)

**Action Items:**

1. Create handoff script (`scripts/handoff_to_ae.py`):

   ```python
   def handoff_qualified_leads():
       # Query leads ready for handoff
       ready_leads = get_handoff_ready_leads()

       for lead in ready_leads:
           # Create contact in HubSpot/Salesforce
           crm_contact_id = hubspot_client.create_contact(lead)

           # Update leads table
           update_lead(lead["id"], {
               "handoff_status": "completed",
               "handoff_at": datetime.now(),
               "crm_contact_id": crm_contact_id
           })

           # Notify AE
           send_slack_notification(
               channel="#sales-handoffs",
               message=f"New qualified lead: {lead['name']} from {lead['company']} - Meeting scheduled for {lead['booking_time']}"
           )
   ```

2. Create Slack webhook (optional but recommended):
   - Go to Slack > Apps > Incoming Webhooks
   - Create webhook URL for #sales-handoffs channel
   - Add to `.env`: `SLACK_WEBHOOK_URL=your_url_here`

3. Generate handoff report:

   ```python
   def generate_handoff_report(lead: dict) -> str:
       report = f"""
       🎯 New Qualified Lead Handoff

       Contact: {lead['name']} ({lead['email']})
       Company: {lead['company']} ({lead['industry']}, {lead['employee_count']} employees)
       Title: {lead['title']}
       Lead Score: {lead['lead_score']}/100

       Enrichment Data:
       - Funding: {lead['funding_stage']} (${lead['funding_amount']}M raised)
       - Tech Stack: {lead['technologies']}
       - Pain Points: {lead['identified_pain_points']}

       Meeting Details:
       - Scheduled: {lead['booking_time']}
       - Duration: 30 minutes
       - Calendly Link: {lead['calendly_url']}

       Outreach History:
       - First Contact: {lead['first_contact_date']}
       - Emails Sent: {lead['emails_sent']}
       - Last Reply: {lead['last_reply_at']} ("{lead['last_reply_preview']}")

       Next Steps:
       1. Review enrichment data and outreach history
       2. Prepare for meeting using pain points identified
       3. Update CRM with meeting outcome
       """
       return report
   ```

4. Schedule handoff automation:
   - **Option A - Immediate:** Trigger on booking confirmation
   - **Option B - Batched:** Daily at 9 AM, send all new handoffs

### 4.4 Feedback Loop (4 hours)

**Goal:** Track AE outcomes to improve SDR system.

**Action Items:**

1. Add outcome tracking to `leads` table:

   ```sql
   ALTER TABLE leads
   ADD COLUMN ae_outcome VARCHAR(50), -- 'qualified_opp', 'not_qualified', 'no_show', 'demo_scheduled'
   ADD COLUMN ae_feedback TEXT,
   ADD COLUMN closed_deal BOOLEAN DEFAULT false,
   ADD COLUMN deal_value DECIMAL(10,2);
   ```

2. Create feedback form (simple for MVP):
   - **Option A - Google Form:** Link in Slack notification
   - **Option B - Internal tool:** Simple web form
   - **Option C - CRM field:** Update directly in HubSpot

3. Analyze feedback:

   ```python
   def analyze_lead_quality():
       query = """
       SELECT
         AVG(lead_score) as avg_score,
         COUNT(*) FILTER (WHERE ae_outcome = 'qualified_opp') as qualified_count,
         COUNT(*) FILTER (WHERE ae_outcome = 'not_qualified') as not_qualified_count,
         COUNT(*) FILTER (WHERE closed_deal = true) as closed_deals,
         AVG(deal_value) FILTER (WHERE closed_deal = true) as avg_deal_value
       FROM leads
       WHERE handoff_status = 'completed'
       """
       # Use results to tune qualification rules
   ```

4. Tune qualification rules based on feedback:
   - If AEs reject leads with score 70-80 → Raise threshold to 80
   - If specific industries convert better → Prioritize those
   - If certain lead sources perform poorly → Deprioritize

---

## Success Metrics

### Week 1 (Core Pipeline):

- ✅ 100% of new leads enriched within 5 minutes
- ✅ 0% duplicate leads in database
- ✅ 80%+ qualification accuracy (manual review of sample)
- ✅ RAG agent returns 10+ enriched fields per lead

### Week 2 (Outreach):

- ✅ 100 emails sent per day
- ✅ 40%+ open rate
- ✅ 10%+ reply rate
- ✅ Copywriter generates unique email for each lead (no generic templates)

### Week 3 (Inbound):

- ✅ 100% of replies detected within 5 minutes
- ✅ 90%+ sentiment classification accuracy
- ✅ Positive replies get booking link within 10 minutes
- ✅ 20%+ of positive replies convert to booked meetings

### Week 4 (Handoff):

- ✅ All booked meetings in CRM within 1 hour
- ✅ AE receives handoff report with meeting prep data
- ✅ 50%+ of handed-off leads marked as "qualified opportunity" by AE
- ✅ Close loop: At least 1 closed deal from SDR automation

---

## Risk Mitigation

### High-Risk Items:

1. **Email Deliverability:**
   - **Risk:** Emails land in spam, low open rates
   - **Mitigation:** Proper domain setup (SPF/DKIM/DMARC), warm up new domain gradually (start with 20 emails/day, increase by 20% daily), avoid spam trigger words

2. **API Rate Limits:**
   - **Risk:** Crunchbase/LinkedIn/SendGrid rate limits block pipeline
   - **Mitigation:** Implement exponential backoff, queue system for retries, monitor rate limit headers, upgrade to paid tiers if needed

3. **Data Quality:**
   - **Risk:** Poor lead sources → low qualification rate → wasted outreach
   - **Mitigation:** Start with high-quality source (Sales Navigator export), manually verify first 50 leads, tune qualification rules based on AE feedback

4. **Reply Detection Failures:**
   - **Risk:** Webhook misses replies, leads slip through
   - **Mitigation:** Backup polling mechanism (check inbox every hour via IMAP), redundant webhook (SendGrid + Postmark), monitor webhook uptime

### Medium-Risk Items:

5. **OpenAI Cost Overruns:**
   - **Risk:** GPT-4 calls for 1000s of leads = high costs
   - **Mitigation:** Use GPT-3.5-turbo for simple tasks (qualification), reserve GPT-4 for copywriting, implement token limits, cache common responses

6. **System Downtime:**
   - **Risk:** Consumer crashes, Redis goes down, leads not processed
   - **Mitigation:** Docker containers with auto-restart, Redis Streams retention (7 days), health check endpoints, Slack alerts on errors

---

## Technical Debt Allowances (MVP Shortcuts)

**Acceptable for MVP:**

- ❌ Manual CSV lead upload (vs. automated discovery API)
- ❌ Calendly link in email (vs. programmatic calendar booking)
- ❌ Daily batch handoff (vs. real-time on booking)
- ❌ Simple sentiment keywords (vs. fine-tuned ML model)
- ❌ Generic error handling (vs. specific retry logic per failure type)

**Must Fix Before Scale:**

- 🔧 Add connection pooling for Supabase (current: new connection per query)
- 🔧 Implement circuit breaker for external APIs (current: retry forever)
- 🔧 Add distributed tracing (current: logs only)
- 🔧 Implement dead letter queue for failed tasks (current: lost on error)

---

## Daily Standups (Recommended)

**Format:** 5-minute check-in at 9 AM daily.

**Questions:**

1. What did I complete yesterday?
2. What am I working on today?
3. Any blockers?

**Example Week 1 Day 3:**

- ✅ Completed: Crunchbase API integration, RAG enrichment tested
- 🚧 Today: Build deduplication agent, test with 100 leads
- ⚠️ Blocker: Need Proxycurl API key (waiting on approval)

---

## Appendix A: Environment Variables Checklist

**Required for MVP:**

```bash
# Core
TENANT_ID=agentic-dev
REDIS_URL=redis://default:<REDIS_PASSWORD>@host:port
SUPABASE_URL=https://project.supabase.co
SUPABASE_ANON_KEY=your-anon-key

# AI/ML
OPENAI_API_KEY=your-openai-api-key

# Enrichment (Phase 0)
CRUNCHBASE_API_KEY=...
PROXYCURL_API_KEY=...  # OR LINKEDIN_ACCESS_TOKEN

# Email (Phase 2)
SENDGRID_API_KEY=...
SENDGRID_FROM_EMAIL=noreply@yourdomain.com

# CRM (Phase 4)
HUBSPOT_API_KEY=...

# Notifications (Optional)
SLACK_WEBHOOK_URL=...
```

---

## Appendix B: File Creation Checklist

**New Files to Create:**

**Phase 0:**

- None (only config updates)

**Phase 1:**

- `config/qualification_rules.py`
- `services/external_apis/apollo_client.py` (if using Apollo)
- `scripts/import_leads_from_csv.py`
- `scripts/daily_lead_discovery.py`
- `tiers/tier_3/deduplication_agent/deduplication.py`
- `tiers/tier_3/deduplication_agent/consumer.py`

**Phase 2:**

- `services/external_apis/email_sender.py`
- `config/outreach_sequences.py`
- `scripts/campaign_metrics.py`
- SQL migration for `outreach_log` table
- SQL migration for `campaigns` table

**Phase 3:**

- `api/webhooks/email_reply.py`
- `services/sentiment_analyzer.py`
- `tiers/tier_3/booking_agent/booking.py`
- `tiers/tier_3/booking_agent/consumer.py`
- `config/auto_responses.py` (optional)
- SQL migration for `bookings` table

**Phase 4:**

- `config/handoff_rules.py`
- `services/external_apis/hubspot_client.py`
- `scripts/handoff_to_ae.py`
- `scripts/daily_handoff_check.py`
- SQL migration to add handoff columns to `leads`

---

## Appendix C: Decision Log

Track key decisions to avoid revisiting:

| Decision             | Options Considered                    | Chosen | Rationale            | Date |
| -------------------- | ------------------------------------- | ------ | -------------------- | ---- |
| Lead Source          | Apollo, CSV Upload, Sales Nav Scraper | TBD    | Pending Week 1 Day 1 | -    |
| Email Service        | SendGrid, Postmark, AWS SES           | TBD    | Pending Week 2 Day 1 | -    |
| Calendar Tool        | Calendly, Cal.com, Google Calendar    | TBD    | Pending Week 3 Day 2 | -    |
| CRM Platform         | HubSpot, Salesforce, Pipedrive        | TBD    | Pending Week 4 Day 1 | -    |
| Scheduling Mechanism | Redis Delayed, Cron, Celery           | TBD    | Pending Week 2 Day 2 | -    |

---

## Appendix D: Testing Strategy

**Unit Tests:**

- RAG agent qualification logic
- Deduplication matching algorithm
- Sentiment analyzer accuracy
- Email template generation

**Integration Tests:**

- Manager → Orchestrator → Agent flow
- External API error handling
- Database write/read operations
- Webhook endpoint responses

**E2E Tests:**

- Full pipeline: CSV → Enrichment → Outreach → Booking → Handoff
- Multi-channel sequence timing
- Reply detection → Sentiment → Action
- CRM sync validation

**Load Tests:**

- 1000 leads/hour enrichment throughput
- 500 emails/hour sending capacity
- Webhook handling 100 replies/hour
- Redis stream consumer lag monitoring

---

## Next Steps

1. **Immediate (Today):**
   - Add Crunchbase + Proxycurl API keys to `.env`
   - Wire Copywriter agent to OpenAI
   - Restart consumers and test enrichment pipeline

2. **Week 1 Kickoff (Monday):**
   - Choose lead source (Apollo vs. CSV)
   - Implement deduplication agent
   - Run E2E test with 10 real leads

3. **Weekly Reviews:**
   - Friday 4 PM: Review week's progress vs. plan
   - Document blockers and decisions
   - Adjust next week's priorities if needed

4. **MVP Launch (Week 5):**
   - Deploy to production environment
   - Monitor first 100 leads through full pipeline
   - Gather AE feedback on first handoffs
   - Iterate based on real-world performance

---

**Document Owner:** Elliot  
**Last Updated:** November 29, 2025  
**Status:** Draft - Awaiting Phase 0 Completion
