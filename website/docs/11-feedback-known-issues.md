# 12 - Feedback & Known Issues

## Feedback should target bot behavior
Use this format:
- command/action
- job ID / event ID
- expected behavior
- actual behavior
- screenshot/time (UTC)

## Suggested categories
- setup
- template UX
- event attendance sync
- payout/finance
- permissions
- reliability/performance

## Known caveats (with fix + why)

### 1) Scheduled Event RSVP sync mismatch
**Caveat:** RSVP count and tracked attendee list may differ.

**How to fix:**
1. Verify bot permissions in guild/channel:
   - View Channels
   - Manage Events
2. Run `/jobs attendance_sync job_id:<id>`.
3. If locked, unlock first:
   - `/jobs attendance_unlock job_id:<id>`
   - `/jobs attendance_sync job_id:<id>`
   - `/jobs attendance_lock job_id:<id>`
4. Validate with `/jobtest event_sync_check job_id:<id>`.

**Why this happens:**
- Missing/insufficient Discord permissions.
- Event link missing or event unavailable.
- Attendance was locked before sync.

---

### 2) Full UI end-to-end testing not always available from bot runtime
**Caveat:** Automated click-path tests through Discord UI may not be runnable directly from this environment.

**How to proceed:**
- Use bot self-test commands:
  - `/jobtest event_sync_check`
  - `/jobtest event_dryrun_payout`
  - `/jobtest event_force_snapshot`
- Or attach Browser Relay for live UI automation when needed.

**Why this happens:**
- Runtime is server-side, not always attached to a live human Discord client UI session.

---

### 3) Confirm payout fails due to empty attendance snapshot
**Caveat:** Event confirm blocks when snapshot has no attendees.

**How to fix:**
1. `/jobs attendance_unlock job_id:<id>`
2. `/jobs attendance_sync job_id:<id>`
3. `/jobs attendance_lock job_id:<id>` (or `/jobtest event_force_snapshot`)
4. Retry `/jobs confirm job_id:<id>`

**Why this happens:**
- Snapshot captured before attendees were synced.
- No RSVP users at snapshot time.

---

### 4) Event template post denied
**Caveat:** User cannot post event template jobs.

**How to fix:**
1. Assign Event Handler role to user.
2. Verify `EVENT_HANDLER_ROLE_ID` in `.env`.
3. Run `/setup status` to confirm config.

**Why this happens:**
- Intentional permission gate: event templates are restricted to Event Handler/Admin.
