# StarCitizen Discord Org Bot

A Discord bot for managing org jobs, payouts, treasury, rep/levels, and account cashouts.

## Documentation & Community

- **Operator Manual (Docusaurus):** [Open Manual](https://sielski666.github.io/StarCitizen-Discord-OrgBot/)
- **Discord support/community:** https://discord.gg/BT8rpuX8R
- **Repo docs source:** `website/docs/`

> Tip: keep this README as a project overview; maintain full operational procedures in Docusaurus docs.

## Features

- **Jobs flow**
  - Post normal jobs with area-first flow (`/jobs post`)
  - Event jobs via templates (`/eventjob post template:<name>`)
  - Event RSVP attendance sync (add/remove from Scheduled Event)
  - Event attendance lock/snapshot + manual attendee correction
  - Complete, payout, cancel, and reopen jobs
- **Account flow**
  - User account overview
  - Buy/sell shares
  - Cashout request flow with persistent approve/reject handling
  - Role/level sync utilities
- **Finance tools**
  - Pending cashouts
  - Recent payouts
  - Cashout lookup
  - User audit and cashout stats
- **Treasury**
  - View treasury status
  - Set treasury balance

## Tech Stack

- Python
- py-cord (`py-cord==2.7.0`)
- SQLite (`aiosqlite`)
- dotenv (`python-dotenv`)

## Project Structure

```text
.
├── bot.py
├── cogs/
│   ├── account.py
│   ├── finance.py
│   ├── jobs.py
│   └── treasury.py
├── services/
│   ├── db.py
│   ├── permissions.py
│   ├── role_sync.py
│   └── tiers.py
├── assets/
├── requirements.txt
└── .env.example
```

## Setup

### 1) Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows PowerShell
```

### 2) Install dependencies

```bash
pip install -r requirements.txt
```

### 3) Configure environment

Copy `.env.example` to `.env` (remove the `.example` suffix).

**Bot token lives in `.env`** and should be set manually:

- `DISCORD_TOKEN=...`

Then configure guild/roles/channels either by:

- editing `.env` directly, or
- running `/setup start` in Discord (admin only)

Required keys used by the bot:

- `GUILD_ID`
- `FINANCE_ROLE_ID`
- `JOBS_ADMIN_ROLE_ID`
- `EVENT_HANDLER_ROLE_ID` (required to restrict event template posting)
- `JOB_CATEGORY_CHANNEL_MAP` (area/category -> channel routing map)
- `JOBS_CHANNEL_ID` (compat/fallback; setup derives this from general map channel)
- `TREASURY_CHANNEL_ID`
- `SHARES_SELL_CHANNEL_ID`
- `FINANCE_CHANNEL_ID` (compat alias; usually same as `TREASURY_CHANNEL_ID`)

Economy/tier values:
- `SHARE_CASHOUT_AUEC_PER_SHARE`
- `LEVEL_PER_REP`
- `REP_PER_JOB_PAYOUT`
- `JOB_TIERS`
- `LEVEL_ROLE_MAP`

### 4) Run

```bash
python bot.py
```

On startup, the bot:

- connects DB
- registers persistent UI views (cashout + job workflow)
- refreshes recent event job cards so attendee display/state is current
- syncs application commands to `GUILD_ID` (if provided)

## Notes

- Keep `.env` private (never commit real tokens/IDs).
- This bot expects role/channel IDs to be valid in the target guild.
- If slash/subcommands don’t show after deploy, restart bot and re-sync commands.

## License

MIT
