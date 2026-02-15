# 06 - Event Jobs

Event jobs are jobs with category `event` and scheduled-event attendance integration.

## Lifecycle
1. Post event template (`/jobs post template:<event-template>`)
2. Bot creates linked Discord Scheduled Event
3. RSVP add/remove auto-syncs attendance
4. Complete job
5. Confirm payout (split across attendance snapshot)

## Important behavior
- Attendance can be locked/unlocked by finance/admin.
- Confirm auto-snapshots + locks if needed.
- Snapshot prevents last-second RSVP changes from affecting payout.
- Closed jobs block attendance sync.

## Event payout logic
- Total reward split across attendees.
- Integer division + remainder distribution.
- Ledger stores payout snapshot details for audit.
