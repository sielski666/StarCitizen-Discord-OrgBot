# 02 - Quick Start

## Baseline checks
- Bot online in server
- `/setup status` clean
- Treasury initialized
- At least one template exists

## First operational flow
1. Create template: `/jobtemplates add`
2. Post job: `/jobs post template:<name>`
3. Claim/complete job
4. Finance/admin confirms with `/jobs confirm`
5. Run `/finance reconcile`

## Event flow quick test
1. Post event template job
2. Confirm scheduled event was created
3. RSVP with test users
4. Run `/jobtest event_sync_check`
5. Complete + confirm payout
