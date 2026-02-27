# 03 - Command Index
<<<<<<< HEAD
=======

This page is the command map. Use the detailed pages for exact usage and behavior.
>>>>>>> a672f116b5385f07234b5109f7c5304b2f702b7c

## Setup
- `/setup start` *(Admin only)*
- `/setup status` *(Admin only)*
- `/setup doctor` *(Admin only)*
- `/setup createchannels` *(Admin only)*

## UI-first boards (preferred for daily use)
- `jobs-board`:
  - **Post Job** (starts area -> tier -> modal flow)
  - **Crew** (opens Add/Remove/View crew tools)
- `stock-board`:
  - **Buy** (modal flow)
  - **Sell** (modal flow + cashout request)
  - **Market** (live snapshot)
- `finance-board`:
  - **Cashout Stats**
  - **Stock Stats**

## Jobs
- `/jobs post` *(Guild members)*
- `/jobs complete` *(Claimer or Admin)*
- `/jobs confirm` *(Finance/Admin only)*
- `/jobs cancel` *(Admin only)*
- `/jobs reopen` *(Admin only)*
- `/jobs attend` *(Guild members)*
- `/jobs unattend` *(Guild members)*
- `/jobs attendees` *(Guild members)*
- `/jobs crew_add` *(Claimer/Jobs Admin/Finance/Admin)*
- `/jobs crew_remove` *(Claimer/Jobs Admin/Finance/Admin)*
- `/jobs crew_list` *(Guild members)*
- `/jobs attendance_sync` *(Finance/Admin only)*
- `/jobs attendance_lock` *(Finance/Admin only)*
- `/jobs attendance_unlock` *(Finance/Admin only)*

## Event jobs
- `/eventjob post template:<name>` *(Guild members)*
- `/eventjob attendee_add job_id member` *(Finance/Admin only)*
- `/eventjob attendee_remove job_id member` *(Finance/Admin only)*
- `/eventjob attendee_list job_id` *(Guild members)*

## Event templates
- `/eventtemplate add` *(Admin only)*
- `/eventtemplate update` *(Admin only)*
- `/eventtemplate clone` *(Admin only)*
- `/eventtemplate list` *(Guild members)*
- `/eventtemplate view` *(Guild members)*
- `/eventtemplate disable` *(Admin only)*
- `/eventtemplate enable` *(Admin only)*
- `/eventtemplate delete` *(Admin only)*

## Job Test
- `/jobtest event_sync_check` *(Admin only)*
- `/jobtest event_dryrun_payout` *(Admin only)*
- `/jobtest event_force_snapshot` *(Admin only)*

## Finance
- `/finance pending_cashouts` *(Finance/Admin only)*
- `/finance recent_payouts` *(Finance/Admin only)*
- `/finance cashout_lookup` *(Finance/Admin only)*
- `/finance user_audit` *(Finance/Admin only)*
- `/finance cashout_stats` *(Finance/Admin only)*
- `/finance stock_stats` *(Finance/Admin only)*
- `/finance reconcile` *(Finance/Admin only)*

## Treasury
- `/treasury status` *(Guild members)*
- `/treasury set` *(Finance/Admin only)*

## Account
- `/account overview` *(Guild members)*
- `/account debugtiers` *(Finance/Admin only)*
- `/account rolesync` *(Finance/Admin only)*

## Bonds
- `/bond redeem` *(Guild members)*

## Stocks
- `/stock buy` *(Guild members)*
- `/stock sell` *(Guild members)*
- `/stock portfolio` *(Guild members)*
- `/stock market` *(Guild members)*
- `/stock price_nudge` *(Finance/Admin only)*
- `/stock price_set` *(Finance/Admin only)*
