# StarCitizen Discord Org Bot

Discord bot for running org operations: jobs, event attendance, payouts, treasury, account progression, and stock/cashout flows.

This README is the **operator quick manual**. Full docs are in `website/docs/` and published at:
- https://sielski666.github.io/StarCitizen-Discord-OrgBot/

---

## What this bot does

- Post and manage jobs (`/jobs post`, complete, confirm, cancel, reopen)
- Run event-template jobs (`/eventjob post template:<name>`) with attendance sync
- Track treasury and finance workflows (cashouts, payout stats, audits)
- Handle account/rep/level utilities
- Provide stock buy/sell + market tooling

---

## 5-minute setup (self-host)

1. **Create bot app/token** in Discord Developer Portal
2. **Invite bot** to your server with admin perms (initial setup)
3. **Clone repo** and enter it
4. **Create venv + install deps**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
5. **Create `.env` from template**
   ```bash
   cp .env.example .env
   ```
6. **Set at minimum** in `.env`:
   - `DISCORD_TOKEN`
   - `GUILD_ID`
7. **Run bot**
   ```bash
   python bot.py
   ```
8. In Discord, run:
   - `/setup start`
   - `/setup status`

If `/setup status` is clean, you are operational.

---

## First live workflow (recommended)

1. Create event template: `/eventtemplate add`
2. Post event job: `/eventjob post template:<name>`
3. Members RSVP in Discord Scheduled Event
4. Complete job and confirm payout: `/jobs confirm`
5. Reconcile finance: `/finance reconcile`

---

## Required config keys (most important)

- `DISCORD_TOKEN`
- `GUILD_ID`
- `FINANCE_ROLE_ID`
- `JOBS_ADMIN_ROLE_ID`
- `EVENT_HANDLER_ROLE_ID`
- `JOB_CATEGORY_CHANNEL_MAP`
- `TREASURY_CHANNEL_ID`
- `STOCK_SELL_CHANNEL_ID` (preferred)

`/setup start` can provision most channels/roles and sync defaults for you.

---

## Core commands

### Setup
- `/setup start`
- `/setup status`
- `/setup doctor`
- `/setup createchannels`

### Jobs
- `/jobs post`, `/jobs complete`, `/jobs confirm`
- `/jobs attendance_sync`, `/jobs attendance_lock`, `/jobs attendance_unlock`

### Event templates/jobs
- `/eventtemplate add|update|list|view|enable|disable|delete`
- `/eventjob post template:<name>`

### Finance/Treasury
- `/finance pending_cashouts`, `/finance recent_payouts`, `/finance reconcile`
- `/treasury status`, `/treasury set`

### Account/Stock
- `/account overview`
- `/stock buy|sell|portfolio|market`

---

## Update safely

### Linux/macOS
```bash
./scripts/update.sh
```

### Windows
```powershell
.\scripts\update.ps1
```

Updater handles pull, deps, compile checks, restart, and rollback on failure.

---

## Troubleshooting quick hits

- **Commands missing:** check bot perms + wait 30–90s after sync
- **Event post denied:** check Event Handler role / `EVENT_HANDLER_ROLE_ID`
- **Attendance mismatch:** run `/jobs attendance_sync`
- **Payout confirm fails:** ensure job is complete + snapshot has attendees

Full troubleshooting: `website/docs/10-troubleshooting.md`

---

## Security notes

- Keep `.env` private
- Never post tokens in screenshots/logs
- Rotate keys immediately if exposed
- Do not commit `.env`

---

## Links

- Operator docs: https://sielski666.github.io/StarCitizen-Discord-OrgBot/
- Invite bot: https://discord.com/oauth2/authorize?client_id=493717180584689665&scope=bot%20applications.commands&permissions=8
- Community/support: https://discord.gg/BT8rpuX8R

## License
MIT
