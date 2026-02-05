# MVP Strengthening Checklist

**Goal:** Wire existing components together so the golden path works end-to-end with real data.

**Last Updated:** February 2026

---

## Gap Summary

| Layer                | Current State                     | Target State                                        | Status  |
| -------------------- | --------------------------------- | --------------------------------------------------- | ------- |
| Gateway `/drafts`    | ~~Returns MOCK_DRAFTS~~           | Queries Supabase `drafts` table                     | ✅ Done |
| Gateway `/mailboxes` | ~~Returns MOCK_MAILBOXES~~        | Queries Supabase `mailboxes` table                  | ✅ Done |
| Gateway `/leads`     | Returns MOCK_LEADS                | Queries Supabase `leads` table                      | ⏳ TODO |
| Gateway `/stats`     | ~~Did not exist~~                 | Aggregates dashboard counts                         | ✅ Done |
| Portal Dashboard     | ~~Hardcoded stats~~               | Fetches from `/api/v1/stats`                        | ✅ Done |
| Portal Inbox         | Local mock state                  | Fetches from `/api/v1/drafts`, calls approve/reject | ⏳ TODO |
| Portal Leads         | Fetches `/api/prospects` (broken) | Fetches from `/api/v1/leads`                        | ⏳ TODO |

---

## Phase 1: Wire Gateway to Supabase (Backend)

### 1.1 Add Supabase client to gateway

- [x] Create `api/gateway/dependencies/supabase.py`
- [x] Initialize client with tenant-scoped RLS
- [x] Add `get_db` dependency with JWT passthrough

### 1.2 Replace mock drafts with real queries

- [x] `GET /drafts` → Query `drafts` table with lead embedding
- [x] `GET /drafts/{id}` → Single draft with lead context
- [x] `POST /drafts/{id}/approve` → Update status, enqueue to Channel Sequencer
- [x] `POST /drafts/{id}/reject` → Update status with reason
- [x] `POST /drafts/{id}/rewrite` → Enqueue regeneration request

### 1.3 Replace mock mailboxes with real queries

- [x] `GET /mailboxes` → Query `mailboxes` table by tenant
- [x] `GET /mailboxes/{id}` → Single mailbox details
- [x] `POST /mailboxes` → Insert with OAuth credentials
- [x] `POST /mailboxes/{id}/reconnect` → Reactivate mailbox
- [x] `POST /mailboxes/{id}/sync` → Trigger sync
- [x] `DELETE /mailboxes/{id}` → Soft delete (deactivate)

### 1.4 Replace mock leads with real queries

- [ ] `GET /leads` → Query `leads` table with filters
- [ ] `GET /leads/{id}` → Single lead with conversation history
- [ ] `PATCH /leads/{id}` → Update lead fields

### 1.5 Add stats endpoint

- [x] `GET /stats` → Full dashboard stats with lead breakdown
- [x] `GET /stats/quick` → Minimal stats for header

---

## Phase 2: Wire Portal to Gateway (Frontend)

### 2.1 Add API client utilities

- [x] Create `apps/portal-customer/src/lib/api.ts` with base fetch wrapper
- [x] Handle auth token injection from Supabase session
- [x] Add typed functions for all endpoints
- [x] Add `apiDelete` helper

### 2.2 Add data fetching hooks

- [x] `useDrafts()` → Fetches from `/api/v1/drafts`
- [x] `usePendingDrafts()` → Convenience wrapper for pending drafts
- [x] `useMailboxes()` → Fetches from `/api/v1/mailboxes`
- [ ] `useLeads()` → Fetches from `/api/v1/leads`
- [x] `useStats()` → Fetches from `/api/v1/stats`
- [x] `useQuickStats()` → Fetches from `/api/v1/stats/quick`

### 2.3 Update Dashboard page

- [x] Replace hardcoded stats with `useStats()`
- [x] Replace hardcoded drafts with `usePendingDrafts()`
- [x] Add loading states for stats and drafts
- [x] Wire approve/reject buttons to API calls
- [x] Empty state for no pending drafts
- [x] Update Monty status with real mailbox count

### 2.4 Update Inbox page

- [ ] Replace mockDrafts with `useDrafts()`
- [ ] Wire approve/reject buttons to API calls
- [ ] Add optimistic updates + error rollback
- [ ] Add loading skeleton + empty state

### 2.5 Update Leads page

- [ ] Replace broken `/api/prospects` with `useLeads()`
- [ ] Wire search/filter to API params
- [ ] Add loading skeleton + empty state

---

## Phase 3: UX Polish (Critical for ROI)

### 3.1 Loading states

- [x] Loading indicators on dashboard stats
- [x] Loading spinner on approve/reject buttons
- [ ] Skeleton loaders for all data tables
- [ ] Page-level loading indicator

### 3.2 Error handling

- [ ] Toast notifications for errors
- [ ] Retry buttons on failed fetches
- [ ] Graceful degradation (show cached data)

### 3.3 Empty states

- [ ] "No drafts pending" illustration + CTA
- [ ] "No leads yet" illustration + CTA
- [ ] "Connect your first mailbox" prompt

### 3.4 Success feedback

- [ ] Toast on approve/reject/send
- [ ] Status badge updates after actions
- [ ] Confetti on first send? (optional)

---

## Phase 4: Verify Golden Path

### 4.1 Manual E2E test script

1. Connect mailbox (or seed test data)
2. Send inbound email to monitored inbox
3. Verify draft appears in portal within 2 min
4. Edit draft content
5. Click Approve & Send
6. Verify sent status + message in DB
7. Check correlation_id traces in logs

### 4.2 Automated smoke test

- [ ] Playwright or Cypress test for approve flow
- [ ] API integration test for draft lifecycle

---

## Priority Order

| Priority | Item                        | Impact            | Effort |
| -------- | --------------------------- | ----------------- | ------ |
| P0       | Gateway Supabase client     | Unblocks all      | Small  |
| P0       | Gateway `/drafts` real data | Core workflow     | Medium |
| P0       | Portal Inbox → API          | Core workflow     | Medium |
| P1       | Gateway `/stats`            | Dashboard value   | Small  |
| P1       | Portal Dashboard → API      | First impression  | Small  |
| P1       | Loading + error states      | Polish            | Medium |
| P2       | Gateway `/leads` real data  | Secondary feature | Medium |
| P2       | Portal Leads → API          | Secondary feature | Medium |
| P2       | Empty states                | Polish            | Small  |

---

## Environment Requirements

```env
# Portal .env.local
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1

# Gateway .env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_JWT_SECRET=your-jwt-secret
```

---

## Files to Create/Modify

### New Files

- `api/gateway/dependencies/supabase.py`
- `apps/portal-customer/src/lib/api.ts`
- `apps/portal-customer/src/hooks/useDrafts.ts`
- `apps/portal-customer/src/hooks/useStats.ts`
- `apps/portal-customer/src/components/ui/skeleton.tsx`
- `apps/portal-customer/src/components/ui/toast.tsx`

### Modified Files

- `api/gateway/routers/drafts.py` (replace mocks)
- `api/gateway/routers/mailboxes.py` (replace mocks)
- `api/gateway/routers/leads.py` (replace mocks)
- `apps/portal-customer/src/app/dashboard/page.tsx`
- `apps/portal-customer/src/app/dashboard/inbox/page.tsx`
- `apps/portal-customer/src/app/dashboard/leads/page.tsx`
