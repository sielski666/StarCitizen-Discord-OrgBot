# 01 - Bot Features (Legacy-Free Reference)

This document is the canonical feature map for the current bot.

If a flow is not listed here, treat it as not supported or legacy.

---

## A) Platform + Core Architecture

- Guild-aware configuration and role-gated operations
- Multi-server support
- Board-first UX (buttons + modals)
- Ledger-backed finance/audit events
- Treasury-aware payout settlement

---

## B) Setup + Server Operations

### Available setup commands
- `/setup start` *(Admin)*
- `/setup status` *(Admin)*
- `/setup doctor` *(Admin)*
- `/setup createchannels` *(Admin)*
- `/setup addarea` *(Admin; modal flow)*

### What setup supports
- Initial server bootstrap
- Validation/diagnostics of config + permissions
- Recreate missing required channels
- Add custom job area + auto-create mapped area channel
- Keep default baseline areas on first setup; add extras later as needed

---

## C) Jobs (Non-Event) — Main Operational Flow

## Posting
- **Only supported posting path:** `Jobs Board → Post Job`
- Area → Tier → Modal creation flow
- Job is routed to mapped area channel

## Job lifecycle
- Open → Claimed → Completed → Paid
- Admin controls:
  - `/jobs cancel`
  - `/jobs reopen`

## Execution controls
- Accept/claim via job card
- Complete via job card
- Confirm payout via finance/admin flow

---

## D) Crew Management (Non-Event)

### UI controls
- Crew button on job/thread control cards:
  - Add Crew
  - Remove Crew
  - View Crew

### Slash controls
- `/jobs crew_add`
- `/jobs crew_remove`
- `/jobs crew_list`

### Behavior
- Mention-first crew input UX
- Crew shown on job cards
- Card refresh on crew changes

---

## E) Payout System

### Payout modes
- Flat Split
- Weighted Split

### Weighted Split capabilities
- Role count selection: **4–8**
- Editable role labels + weights
- Non-negative weights (`>= 0`)
- Assignment validation:
  - only payout-group members
  - no duplicates across roles
  - every participant assigned exactly once

### Weighted audit
- Writes ledger snapshot:
  - `job_weighted_snapshot`
  - includes labels/weights/assignments

### Treasury + shortfall support
- Treasury-aware settlement path
- If shortfall occurs: outstanding payout can be issued as bond

---

## F) Bonds

- `/bond redeem`
- FIFO redemption behavior
- Treasury-safe redemption constraints

---

## G) Event Jobs

### Event posting
- `/eventjob post template:<name>`

### Attendance (member)
- `/jobs attend`
- `/jobs unattend`
- `/jobs attendees`

### Attendance controls (finance/admin)
- `/jobs attendance_sync`
- `/jobs attendance_lock`
- `/jobs attendance_unlock`

### Manual attendee admin
- `/eventjob attendee_add`
- `/eventjob attendee_remove`
- `/eventjob attendee_list`

### Event payout model
- Payout based on attendance snapshot/lock flow

---

## H) Event Templates

- `/eventtemplate add`
- `/eventtemplate update`
- `/eventtemplate clone`
- `/eventtemplate list`
- `/eventtemplate view`
- `/eventtemplate disable`
- `/eventtemplate enable`
- `/eventtemplate delete`

---

## I) Finance + Treasury + Audit Commands

### Finance
- `/finance pending_cashouts`
- `/finance recent_payouts`
- `/finance cashout_lookup`
- `/finance user_audit`
- `/finance cashout_stats`
- `/finance stock_stats`
- `/finance reconcile`

### Treasury
- `/treasury status`
- `/treasury set`

---

## J) Account + Role Sync

- `/account overview`
- `/account debugtiers`
- `/account rolesync`

---

## K) Stocks

- `/stock buy`
- `/stock sell`
- `/stock portfolio`
- `/stock market`
- `/stock price_nudge`
- `/stock price_set`

---

## L) Reliability + Guardrail Improvements (Current)

- Board-only posting model (legacy `/jobs post` removed)
- Channel routing guardrails prevent silent wrong-channel posting
- Legacy job lookup compatibility across restart scope differences
- Weighted payout interaction flow hardened for Discord component/modal limits

---

## M) Legacy/Removed (Do Not Use)

- `/jobs post`
- Any docs/instructions saying “post jobs with `/jobs post`”
- Any docs/instructions saying “use jobs-board Crew button”

This feature map replaces those legacy instructions.
