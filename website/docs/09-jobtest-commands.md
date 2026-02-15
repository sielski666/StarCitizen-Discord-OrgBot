# 10 - Job Test Commands (Admin)

These commands help validate event-job flows without paying live rewards immediately.

## `/jobtest event_sync_check job_id:<id>`
Checks:
- linked scheduled event exists
- subscriber count vs tracked attendee count

Use when attendance looks wrong.

## `/jobtest event_dryrun_payout job_id:<id>`
Previews payout split without applying payouts.

Use before confirmation to verify fairness and totals.

## `/jobtest event_force_snapshot job_id:<id>`
Performs:
1. unlock attendance
2. sync from event RSVPs
3. create snapshot
4. lock attendance

Use before final confirm when you need a controlled payout set.
