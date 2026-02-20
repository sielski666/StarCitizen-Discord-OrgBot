# 03 - Command Index

## Setup
- `/setup start`
- `/setup status`
- `/setup doctor`
- `/setup createchannels`

## UI-first boards (preferred for daily use)
- `jobs-board`:
  - **Post Job** (starts area -> tier -> modal flow)
- `stock-board`:
  - **Buy** (modal flow)
  - **Sell** (modal flow + cashout request)
  - **Market** (live snapshot)
- `finance-board`:
  - **Cashout Stats**
  - **Stock Stats**

## Jobs
- `/jobs post`
- `/jobs complete`
- `/jobs confirm`
- `/jobs cancel`
- `/jobs reopen`
- `/jobs attend`
- `/jobs unattend`
- `/jobs attendees`
- `/jobs crew_add`
- `/jobs crew_remove`
- `/jobs crew_list`
- `/jobs attendance_sync`
- `/jobs attendance_lock`
- `/jobs attendance_unlock`

## Event jobs
- `/eventjob post template:<name>`
- `/eventjob attendee_add job_id member` (finance/admin)
- `/eventjob attendee_remove job_id member` (finance/admin)
- `/eventjob attendee_list job_id`

## Event templates
- `/eventtemplate add`
- `/eventtemplate update`
- `/eventtemplate clone`
- `/eventtemplate list`
- `/eventtemplate view`
- `/eventtemplate disable`
- `/eventtemplate enable`
- `/eventtemplate delete`

## Job Test (admin)
- `/jobtest event_sync_check`
- `/jobtest event_dryrun_payout`
- `/jobtest event_force_snapshot`

## Finance
- `/finance pending_cashouts`
- `/finance recent_payouts`
- `/finance cashout_lookup`
- `/finance user_audit`
- `/finance cashout_stats`
- `/finance stock_stats`
- `/finance reconcile`

## Treasury
- `/treasury status`
- `/treasury set`

## Account
- `/account overview`
- `/account debugtiers`
- `/account rolesync`

## Bonds
- `/bond redeem`

## Stocks
- `/stock buy`
- `/stock sell`
- `/stock portfolio`
- `/stock market`
- `/stock price_nudge` (finance/admin)
- `/stock price_set` (finance/admin)