# Setup

## Primary setup command
`/setup start` (Admin)

What it does:
- Ensures channels exist (`jobs`, `treasury`, `share-sell-confirm`)
- Ensures `Event Handler` role exists
- Syncs IDs into `.env`
- Sets compatibility `FINANCE_CHANNEL_ID` to treasury channel

After running setup, restart bot service:
```bash
sudo systemctl restart starcitizen-orgbot
```

## Validation commands
- `/setup status` -> checks required config presence
- `/setup createchannels` -> re-ensure channels only

## Setup lifecycle
1. Run `/setup start`
2. Assign users to Finance / Jobs Admin / Event Handler roles
3. Create templates via `/jobtemplates add`
4. Start operations (`/jobs post`, `/jobs confirm`, finance workflows)
