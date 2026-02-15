# 02 - Setup Commands

Run setup commands after quick start and before production use.

## Step 1 — Run setup command
`/setup start` (Admin)

This command:
- ensures required channels (`jobs`, `treasury`, `share-sell-confirm`)
- ensures `Event Handler` role exists
- writes/syncs IDs to `.env`
- updates config for newer setup flow (event-handler support + channel/env sync)

## Step 2 — Validate setup
`/setup status`

Check all required fields are present.

## Step 3 — Create channels only (optional)
`/setup createchannels`

Use if channels were deleted or changed.

## Step 4 — Restart bot
```bash
sudo systemctl restart starcitizen-orgbot
sudo systemctl status starcitizen-orgbot --no-pager
```

## Step 5 — Assign roles
Assign appropriate members:
- Finance role
- Jobs Admin role
- Event Handler role
