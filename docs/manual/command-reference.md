# Command Reference

This page lists all current slash command groups and what each command does.

## `/setup` (Admin)
- `/setup start` — auto-setup channels + Event Handler role + env sync
- `/setup status` — show current setup values and missing keys
- `/setup createchannels` — create/validate required channels

## `/jobs`
- `/jobs post [template]` — create a job (template optional; modal flow)
- `/jobs complete job_id` — mark claimed job completed (claimer/admin)
- `/jobs confirm job_id` — confirm payout (finance/admin)
- `/jobs cancel job_id` — cancel job (admin)
- `/jobs reopen job_id` — reopen cancelled job (admin)

### Event attendance controls
- `/jobs attend job_id` — join event attendance list
- `/jobs unattend job_id` — leave event attendance list
- `/jobs attendees job_id` — list tracked attendees
- `/jobs attendance_sync job_id` — force sync from scheduled-event RSVPs (finance/admin)
- `/jobs attendance_lock job_id` — lock attendance (finance/admin)
- `/jobs attendance_unlock job_id` — unlock attendance (finance/admin)

## `/jobtemplates`
- `/jobtemplates add` — create template via modal (admin)
- `/jobtemplates update name` — update template via modal (admin)
- `/jobtemplates clone source_name new_name` — clone template (admin)
- `/jobtemplates list [include_inactive]` — list templates
- `/jobtemplates view name` — view one template
- `/jobtemplates disable name` — disable template (admin)
- `/jobtemplates enable name` — enable template (admin)
- `/jobtemplates delete name` — delete template (admin)

## `/jobtest` (Admin self-test)
- `/jobtest event_sync_check job_id` — compare linked event subscribers vs tracked attendees
- `/jobtest event_dryrun_payout job_id` — preview split payout (no payment)
- `/jobtest event_force_snapshot job_id` — sync RSVPs, snapshot, and lock attendance

## `/finance`
- `/finance pending_cashouts` — pending/approved cashout list
- `/finance recent_payouts` — recent payout + rep tx
- `/finance cashout_lookup request_id` — lookup one cashout
- `/finance user_audit user` — user transaction audit
- `/finance cashout_stats` — cashout counts + treasury snapshot
- `/finance reconcile` — compare current treasury vs ledger-derived treasury

## `/treasury`
- `/treasury status` — current treasury amount
- `/treasury set amount` — set treasury amount (finance/admin)

## `/account`
- `/account overview` — user org credits/shares/rep/level/tier
- `/account buyshares amount` — buy shares using org credits
- `/account sellshares amount` — cashout request (locks shares)
- `/account debugtiers user` — tier role audit (finance/admin)
- `/account rolesync [user]` — sync level tier roles (finance/admin)
