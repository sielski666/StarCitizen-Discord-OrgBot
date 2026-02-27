# 02 - Setup Commands

Run setup before production use.

## Step 1 — Run setup
`/setup start` (Admin)

<<<<<<< HEAD
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
=======
This command:
- ensures required channels (`jobs`, `treasury`, `share-sell-confirm`)
- ensures `Event Handler` role exists
- saves/syncs guild settings for current server
- updates config for newer setup flow (event-handler support + channel/env sync)
>>>>>>> a672f116b5385f07234b5109f7c5304b2f702b7c

## Step 2 — Validate
`/setup status`

Check channels, roles, and stock config values.

## Step 3 — Channel repair only (optional)
`/setup createchannels`

Use if channels were deleted/moved.

<<<<<<< HEAD
## Step 4 — Diagnose if needed
`/setup doctor`
=======
## Step 4 — Continue setup
No restart is needed for hosted usage. Continue with role assignment and validation.
>>>>>>> a672f116b5385f07234b5109f7c5304b2f702b7c

Runs permission/config checks and suggests fixes.

<<<<<<< HEAD
## Notes
- Hosted users do not need to restart anything after setup.
- Self-host users restart only when deployment/config changes require it.
=======
## Step 6 — Set org logo (job card thumbnail)
The top-right logo on job cards uses:

- `assets/org_logo.png`

To change it:
1. Replace `assets/org_logo.png` with your org image.
2. If you are using the hosted bot, ask the operator to apply the logo update.

If the file is missing, cards will send without a custom thumbnail logo.
>>>>>>> a672f116b5385f07234b5109f7c5304b2f702b7c
