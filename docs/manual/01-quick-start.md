# 01 - Quick Start

## Baseline checks
- Copy `.env.example` -> `.env` (remove `.example` suffix)
- Manually set `DISCORD_TOKEN` in `.env`
- Bot online in server
- `/setup status` clean
- Treasury initialized
- At least one event template exists

## First operational flow
1. Create event template: `/eventtemplate add`
2. Post event job: `/eventjob post template:<name>`
3. Claim/complete job
4. Finance/admin confirms with `/jobs confirm`
5. Run `/finance reconcile`

## Non-event flow quick test
1. Run `/jobs post`
2. Choose area then tier
3. Submit modal
4. Confirm job routes to expected area channel
