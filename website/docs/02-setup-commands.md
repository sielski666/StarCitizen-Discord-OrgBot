# 02 - Setup Commands

Run setup before production use.

## Step 1 — Run setup
`/setup start` (Admin)

This now:
- ensures required channels (`jobs`, `treasury`, `stock-sell-confirm`, `stock-market`)
- ensures board channels (`jobs-board`, `stock-board`, `finance-board`)
- deploys/refreshes board messages in those board channels
- ensures required roles (`Finance`, `Jobs Admin`, `Event Handler`)
- syncs guild settings
- writes stock config defaults if missing:
  - `STOCK_ENABLED`
  - `STOCK_BASE_PRICE`
  - `STOCK_MIN_PRICE`
  - `STOCK_MAX_PRICE`
  - `STOCK_DAILY_MOVE_CAP_BPS`
  - `STOCK_DEMAND_SENSITIVITY_BPS`

## Step 2 — Validate
`/setup status`

Check channels, roles, and stock config values.

## Step 3 — Channel repair only (optional)
`/setup createchannels`

Use if channels were deleted/moved.

## Step 4 — Diagnose if needed
`/setup doctor`

Runs permission/config checks and suggests fixes.

## Notes
- Hosted users do not need to restart anything after setup.
- Self-host users restart only when deployment/config changes require it.