## Website updates tracker (as of Feb 1, 2026)

This file tracks which UX/design updates have been implemented.

Legend:

- ✅ Completed
- ⏳ Pending

---

## 🟢 Minor updates (Quick wins)

1. Brand consistency (“Monty by AgentFlow”)

- ✅ Completed — marketing nav now shows “Monty” + “by AgentFlow”

2. Navigation pill copy

- ✅ Completed — “For sales teams” / “For agencies”

3. CTA trust micro-copy

- ✅ Completed — added “No credit card required / Setup takes 2 minutes / Personal onboarding included” beneath hero CTAs

4. Dashboard preview interactivity + portal likeness

- ✅ Completed — marketing preview now includes portal-style stats + “pending drafts” list with hover-revealed context and Review button

5. Sticky CTA urgency

- ✅ Completed — sticky bar copy updated to “This week’s cohort nearly full”

---

## 🟡 Moderate updates (Medium effort, high impact)

6. Social proof / testimonials section

- ⏳ Pending

7. “How it works” step 2 simplification

- ✅ Completed — step 2 copy simplified to “Monty drafts replies in your voice”

8. Portal dashboard AI / agent status

- ✅ Completed — added “Monty status” card to the portal dashboard (Active, monitoring inboxes, drafts ready, next check)

9. Pricing mini-FAQ beneath plans

- ✅ Completed — added a 3-item mini-FAQ under pricing

10. Live demo / playground CTA

- ✅ Completed — added “Try the live demo” CTA next to the demo button

---

## 🔴 Major updates (Strategic)

### 11. **Mobile Experience Needs Attention**

**Issue:** The hero split layout doesn't adapt well to mobile. The orb gets small, and the parallax loses impact.

**Recommendations:**

- On mobile, stack: content first, orb below (or as a background element)
- Simplify the orb animation on mobile (reduce blur/layers for performance)
- Ensure the dashboard preview scrolls horizontally on mobile

---

### 12. **Add Personalization Based on Referral Source**

**Issue:** Everyone sees the same page regardless of where they came from.

**Strategic opportunity:**

- If user comes from LinkedIn ad targeting SDRs → Show SDR-focused copy
- If from a cold email about founders → Lead with "Only step in for the final close"
- Use URL params (`?persona=sdr`) to customize hero text

---

### 13. **The Orb Should Feel More "Alive" and Contextual**

- ✅ Completed — marketing hero speech bubble now rotates through live statuses and the orb reflects state subtly.

**Issue:** The orb is beautiful but purely decorative. It doesn't communicate anything.

**Make it meaningful:**

- Orb pulses when "thinking" (simulating AI processing)
- Orb glows green when "ready" vs amber when "drafting"
- Speech bubble could cycle through different states:
  - "Monty drafted 3 replies for you"
  - "Checking your inbox now..."
  - "New lead detected: Sarah from Acme"

---

### 14. **Login/Portal: Add Onboarding Progress**

- ✅ Completed — added a “Get started with Monty” checklist card on the portal dashboard.

**Issue:** After signup, users land in a dashboard with mock data. There's no guidance.

**Add an onboarding checklist:**

```
Get started with Monty (2/4 complete)
✅ Connect your inbox
✅ Set your voice preferences
⬜ Approve your first draft
⬜ Enable autopilot mode
```

---

### 15. **Add a "Use Case" Section with Specific Scenarios**

- ✅ Completed — added a dedicated “Use cases” section (cold outreach, follow-ups, inbound qualification) on the marketing page.

**Issue:** The "Built for" section is good but could be richer.

**Expand with concrete scenarios:**

```
📧 Cold Outreach
"You upload a lead list. Monty researches each prospect, writes personalized
 first touches, and sends on your schedule."

🔄 Follow-Up Sequences
"Monty tracks who hasn't replied and sends perfectly-timed follow-ups—up to
 5 touches per lead."

📥 Inbound Qualification
"A lead emails you. Monty qualifies them, drafts a response, and books a call
 if they're a fit."
```

---

## 📋 Implementation Priority

| Priority | Update                              | Effort | Impact    |
| -------- | ----------------------------------- | ------ | --------- |
| 1        | Brand consistency (AgentFlow/Monty) | Low    | High      |
| 2        | Fix nav pill copy                   | Low    | Medium    |
| 3        | Add trust micro-copy near CTAs      | Low    | Medium    |
| 4        | Add testimonials section            | Medium | High      |
| 5        | Add AI status to dashboard          | Medium | High      |
| 6        | Make orb contextual/alive           | Medium | High      |
| 7        | Mobile optimization                 | Medium | High      |
| 8        | Add interactive demo/playground     | High   | Very High |
| 9        | Onboarding checklist in portal      | Medium | High      |
| 10       | Use case scenarios expansion        | Low    | Medium    |

---

Would you like me to implement any of these updates? I can start with the quick wins (brand consistency, nav pills, trust signals) or tackle a bigger item like adding the AI status component to the dashboard or making the orb more contextual.
