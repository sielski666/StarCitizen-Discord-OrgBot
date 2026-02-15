# Troubleshooting

## Slash commands missing
- Restart bot service
- Verify bot has correct permissions in guild
- Confirm `GUILD_ID` and sync path are correct

## Event template cannot be posted
- Confirm user has Event Handler role or Admin
- Confirm `EVENT_HANDLER_ROLE_ID` in `.env` is correct
- Run `/setup status`

## Event attendance mismatch
- Run `/jobs attendance_sync job_id:<id>`
- If locked, unlock first
- Use `/jobtest event_sync_check job_id:<id>`

## Confirm payout blocked
- Ensure job status is `completed`
- Ensure attendance snapshot has members
- Use `/jobtest event_dryrun_payout` to inspect split before confirm

## Setup issues
- `/setup start` failed role/channel create: check bot permissions:
  - Manage Roles
  - Manage Channels
  - Manage Events

## Service diagnostics
```bash
sudo systemctl status starcitizen-orgbot --no-pager
sudo journalctl -u starcitizen-orgbot -n 200 --no-pager
```
