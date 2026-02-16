# 10 - Troubleshooting


## Commands missing in Discord
- verify bot permissions
- verify command sync and guild context
- wait 30–90 seconds after invite/setup, then check again

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

## Service issues (hosted users)
If you suspect service/runtime issues, contact the bot operator with:
- server (guild) ID
- command used
- exact error text/screenshot
- timestamp (UTC)
