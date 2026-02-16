# 02 - Setup Commands

Run setup commands after quick start and before production use.

## Step 1 — Run setup command
`/setup start` (Admin)

This command:
- ensures required channels (`jobs`, `treasury`, `share-sell-confirm`)
- ensures `Event Handler` role exists
- saves/syncs guild settings for current server
- updates config for newer setup flow (event-handler support + channel/env sync)

## Step 2 — Validate setup
`/setup status`

Check all required fields are present.

## Step 3 — Create channels only (optional)
`/setup createchannels`

Use if channels were deleted or changed.

## Step 4 — Continue setup
No restart is needed for hosted usage. Continue with role assignment and validation.

## Step 5 — Assign roles
Assign appropriate members:
- Finance role
- Jobs Admin role
- Event Handler role

## Step 6 — Set org logo (job card thumbnail)
The top-right logo on job cards uses:

- `assets/org_logo.png`

To change it:
1. Replace `assets/org_logo.png` with your org image.
2. If you are using the hosted bot, ask the operator to apply the logo update.

If the file is missing, cards will send without a custom thumbnail logo.
