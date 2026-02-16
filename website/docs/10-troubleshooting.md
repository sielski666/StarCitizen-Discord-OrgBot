# 11 - Troubleshooting


## Commands missing in Discord
- restart service
- verify bot permissions
- verify command sync and guild context

## Event template post denied
- user needs Event Handler role or Admin
- verify `EVENT_HANDLER_ROLE_ID`

## Attendance mismatch
- run `/jobs attendance_sync`
- if locked, unlock first
- verify with `/jobtest event_sync_check`

## Confirm payout fails
- confirm job is `completed`
- ensure snapshot is not empty
- dry run with `/jobtest event_dryrun_payout`

## Service logs
```bash
sudo systemctl status starcitizen-orgbot --no-pager
sudo journalctl -u starcitizen-orgbot -n 200 --no-pager
```