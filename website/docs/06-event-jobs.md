# 06 - Event Jobs

Event jobs are jobs with category `event` and scheduled-event attendance integration.

## Lifecycle
1. Post event template (`/eventjob post template:<event-template>`)
2. Bot creates linked Discord Scheduled Event
3. RSVP add/remove auto-syncs attendance
4. Event starts -> attendance snapshot locks
5. Event ends -> ready for finance/admin confirmation payout
6. Confirm payout (split across attendance snapshot)

## Important behavior
- Event jobs are RSVP-driven (no claim path).
- Open event cards show participants and status: **On-boarding / accepting participants**.
- Locked event cards show: **No longer accepting participants**.
- Attendance can be locked/unlocked by finance/admin.
- Confirm auto-snapshots + locks if needed.
- Snapshot prevents last-second RSVP changes from affecting payout.
- Closed jobs block attendance sync.
- Finance/admin can manually correct attendance before payout:
  - `/eventjob attendee_add`
  - `/eventjob attendee_remove`
  - `/eventjob attendee_list`

## Event payout logic
- Total reward split across attendees.
- Integer division + remainder distribution.
- Ledger stores payout snapshot details for audit.
