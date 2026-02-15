# 04 - Jobs Commands

## `/jobs post`
**Who:** guild members

**How to use:**
- Run `/jobs post`
- Choose area -> choose tier -> fill modal

**What it does:**
- Creates a non-event job card routed to the mapped area channel.
- Reserves escrow from available treasury at job creation.

> Event jobs are posted with `/eventjob post template:<name>`.

---

## `/jobs complete job_id:<id>`
**Who:** claimer or admin (non-event jobs)

**How to use:**
- Run after work is done.

**What it does:**
- Moves job to `completed`.
- Finance/admin can then confirm payout.

---

## `/jobs confirm job_id:<id>`
**Who:** finance/admin

**How to use:**
- Run only after completion.

**What it does:**
- Marks job paid (idempotent-safe state transition first).
- Non-event job: pays claimer.
- Event job: pays attendance snapshot split.
- Adds rep and role-sync per payout target.
- Releases escrow and writes ledger entries.

---

## `/jobs cancel job_id:<id>`
**Who:** admin

**What it does:**
- Cancels active job.
- Releases reserved escrow back to available treasury.

## `/jobs reopen job_id:<id>`
**Who:** admin

**What it does:**
- Reopens cancelled job to `open`.

---

## Event attendance commands

### `/jobs attend job_id:<id>`
Adds yourself to event attendance list.

### `/jobs unattend job_id:<id>`
Removes yourself from event attendance list.

### `/jobs attendees job_id:<id>`
Shows tracked attendees.

### `/jobs attendance_sync job_id:<id>`
**Who:** finance/admin

Force-sync attendance from Scheduled Event RSVPs.

### `/jobs attendance_lock job_id:<id>`
**Who:** finance/admin

Lock attendance to prevent changes.

### `/jobs attendance_unlock job_id:<id>`
**Who:** finance/admin

Unlock attendance for changes/sync.
