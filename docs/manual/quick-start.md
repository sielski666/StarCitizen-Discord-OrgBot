# Quick Start

## 1) Prerequisites
- Bot invited to guild with required permissions (manage roles/channels/events as needed).
- `.env` configured at minimum with token and guild role/channel IDs.

## 2) Baseline `.env` keys
- `DISCORD_TOKEN`
- `GUILD_ID`
- `FINANCE_ROLE_ID`
- `JOBS_ADMIN_ROLE_ID`
- `EVENT_HANDLER_ROLE_ID`
- `JOBS_CHANNEL_ID`
- `TREASURY_CHANNEL_ID`
- `SHARES_SELL_CHANNEL_ID`
- `FINANCE_CHANNEL_ID` (usually treasury channel)
- Economy settings: `SHARE_CASHOUT_AUEC_PER_SHARE`, `LEVEL_PER_REP`, `REP_PER_JOB_PAYOUT`, `JOB_TIERS`, `LEVEL_ROLE_MAP`

## 3) Start/restart service
```bash
sudo systemctl restart starcitizen-orgbot
sudo systemctl status starcitizen-orgbot --no-pager
```

## 4) In Discord (admin)
- `/setup start`
- `/setup status`

## 5) Smoke test
- `/jobtemplates list`
- `/finance reconcile`
- `/treasury status`
- Post one test job with `/jobs post`
