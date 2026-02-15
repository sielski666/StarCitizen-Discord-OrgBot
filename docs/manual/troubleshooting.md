# Troubleshooting

## Commands not appearing
- restart bot service
- verify guild sync and permissions

## Event attendance mismatch
- run `/jobs attendance_sync job_id:<id>`
- if locked, unlock first
- use `/jobtest event_sync_check` to compare RSVP vs tracked

## Confirm fails on event job
- ensure job status is `completed`
- ensure attendance snapshot is populated
- if empty, run sync or force snapshot tools

## Service diagnostics
```bash
sudo systemctl status starcitizen-orgbot --no-pager
sudo journalctl -u starcitizen-orgbot -n 150 --no-pager
```
