# Event Jobs

Event jobs are category `event` templates/jobs linked to Discord Scheduled Events.

## End-to-end flow
1. Event Handler/Admin runs `/jobs post template:<event-template>`
2. Bot creates job + linked Scheduled Event
3. RSVP add/remove auto-syncs into job attendance
4. Claimer/admin marks job complete
5. Finance/admin confirms -> payout split across attendance snapshot

## Attendance behavior
- Auto-sync from Scheduled Event RSVP listeners
- Manual visibility: `/jobs attendees job_id:<id>`
- Optional force-sync: `/jobs attendance_sync job_id:<id>`
- Optional lock/unlock:
  - `/jobs attendance_lock job_id:<id>`
  - `/jobs attendance_unlock job_id:<id>`

## Snapshot safety
At confirm time:
- if unlocked, bot snapshots and locks attendance automatically
- payout uses snapshot (not live mutable list)
- prevents last-second RSVP race condition affecting payout

## Payout math
Total reward is divided across attendees:
- base = reward // attendee_count
- remainder distributed +1 to first N attendees

## Self-test commands (Admin)
- `/jobtest event_sync_check job_id:<id>`
- `/jobtest event_dryrun_payout job_id:<id>`
- `/jobtest event_force_snapshot job_id:<id>`
