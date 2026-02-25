# 10 - Troubleshooting (Operator Playbook)

Use this when something breaks. Each section is symptom -> cause -> fix.

## 1) Slash commands not showing

**Likely causes**
- Bot missing permissions
- Guild command sync delay
- Wrong guild configured

**Fix**
1. Verify bot is in the correct server
2. Verify `GUILD_ID` in `.env`
3. Restart bot
4. Wait 30–90 seconds
5. Run `/setup status`

---

## 2) `/setup start` fails or partially completes

**Likely causes**
- Missing admin permissions
- Missing channel/role creation permissions

**Fix**
1. Ensure your user has Admin
2. Ensure bot role is high enough in role hierarchy
3. Re-run `/setup start`
4. Run `/setup doctor`

---

## 3) Event template post denied

**Likely causes**
- User lacks Event Handler role
- Wrong `EVENT_HANDLER_ROLE_ID`

**Fix**
1. Assign Event Handler role to poster
2. Check `EVENT_HANDLER_ROLE_ID`
3. Run `/setup status`

---

## 4) Attendance mismatch (RSVP vs bot list)

**Likely causes**
- Attendance lock enabled too early
- Discord event permissions missing
- Event link missing/stale

**Fix**
1. `/jobs attendance_unlock job_id:<id>`
2. `/jobs attendance_sync job_id:<id>`
3. `/jobs attendance_lock job_id:<id>`
4. Verify with `/jobtest event_sync_check job_id:<id>`

---

## 5) `/jobs confirm` payout fails

**Likely causes**
- Job not completed
- Empty attendance snapshot

**Fix**
1. Confirm job state is completed
2. Refresh snapshot (unlock -> sync -> lock)
3. Retry `/jobs confirm`
4. Use `/jobtest event_dryrun_payout job_id:<id>` if needed

---

## 6) Bot online but no responses

**Likely causes**
- Runtime error loop
- Token invalid/expired
- DB lock or file permission issue

**Fix**
1. Check logs for traceback
2. Verify `DISCORD_TOKEN`
3. Verify file perms for DB path
4. Restart process/service

---

## 7) Update broke behavior

**Fix (Linux/macOS)**
```bash
./scripts/update.sh
```
This includes rollback on failed update.

**Fix (Windows)**
```powershell
.\scripts\update.ps1
```

---

## What to send when requesting support

- Guild ID
- Command used
- Job/event ID if relevant
- Exact error text
- Timestamp (UTC)
- Screenshot/log snippet
