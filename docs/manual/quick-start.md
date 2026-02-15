# Quick Start

## 1) Configure `.env`
Required baseline:
- `DISCORD_TOKEN`
- `GUILD_ID`
- `FINANCE_ROLE_ID`
- `JOBS_ADMIN_ROLE_ID`
- `EVENT_HANDLER_ROLE_ID`
- `JOBS_CHANNEL_ID`
- `TREASURY_CHANNEL_ID`
- `SHARES_SELL_CHANNEL_ID`

## 2) Start service
```bash
sudo systemctl restart starcitizen-orgbot
sudo systemctl status starcitizen-orgbot --no-pager
```

## 3) In Discord (admin)
- Run `/setup start`
- Run `/setup status`

## 4) Sanity checks
- `/jobtemplates list`
- `/finance reconcile`
- Post one test job with `/jobs post`
