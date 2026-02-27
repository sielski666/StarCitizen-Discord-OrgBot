<<<<<<< HEAD
# 01 - Start Here (Beginner Guide)
=======
# 01 - Startup Information
>>>>>>> a672f116b5385f07234b5109f7c5304b2f702b7c

If this is your first time running the bot, do this page top-to-bottom.

<<<<<<< HEAD
## What success looks like
=======
## Start here
For hosted multi-server usage, server admins only need to:
1. Run `/setup start`
2. Run `/setup status`
>>>>>>> a672f116b5385f07234b5109f7c5304b2f702b7c

After setup, you should be able to:
1. Run `/setup status` with no critical errors
2. Post a job (`/jobs post`)
3. Create + post an event template job (`/eventtemplate add` + `/eventjob post`)
4. Confirm payout flow works (`/jobs confirm`)

---

## Prerequisites

- Discord server where you are Admin
- Discord bot token from Developer Portal
- Python 3.10+
- Terminal access on your host machine

---

## Step-by-step setup

### 1) Install and run the bot

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set at least:
- `DISCORD_TOKEN`
- `GUILD_ID`

Start:
```bash
python bot.py
```

### 2) Run Discord setup

In your server:
- `/setup start`
- `/setup status`

`/setup start` will create required channels/roles and apply defaults.

### 3) Validate core flow

- `/eventtemplate add`
- `/eventjob post template:<name>`
- RSVP via linked scheduled event
- Complete + confirm job (`/jobs confirm`)

### 4) Validate non-event flow

- `/jobs post`
- Pick area and tier
- Submit modal
- Confirm it routes to the expected channel

---

## Feature map (plain English)

- **Setup**: provisions channels/roles/config sanity checks
- **Jobs**: creates and tracks org work from posted to paid
- **Event Jobs**: ties job attendance to Discord event RSVP
- **Finance**: cashout/payout audit and reconciliation tools
- **Treasury**: current treasury state + admin adjustment
- **Account**: per-user overview and progression
- **Stocks**: buy/sell market layer and admin controls

---

## Where to go next

- Setup commands: `02-setup-commands.md`
- Command index: `03-command-index.md`
- Troubleshooting: `10-troubleshooting.md`
- FAQ: `16-faq.md`
