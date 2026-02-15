# Event Jobs

## Flow
1. Post event template job: `/jobs post template:<event-template>`
2. Bot auto-creates linked Discord Scheduled Event
3. RSVP add/remove auto-syncs to job attendance
4. Complete job -> finance/admin confirms payout
5. Reward split is distributed to attendance snapshot

## Attendance controls
- `/jobs attendees job_id:<id>`
- `/jobs attendance_sync job_id:<id>`
- `/jobs attendance_lock job_id:<id>`
- `/jobs attendance_unlock job_id:<id>`

## Admin self-test tools
- `/jobtest event_sync_check job_id:<id>`
- `/jobtest event_dryrun_payout job_id:<id>`
- `/jobtest event_force_snapshot job_id:<id>`

## Safety behavior
- Attendance can be locked
- Confirm snapshots attendance before payout (if not locked already)
- Closed events (paid/cancelled) block attendance sync
- Event payout writes ledger snapshot details
