# Handover Notes (AWS -> Mac) — 2026-02-17

Purpose: quick refresher for the Mac instance about what was changed on AWS/bot side.

## Infrastructure / Runtime
- Confirmed AWS bot service repeatedly healthy after restarts:
  - `starcitizen-orgbot.service` active/running.
- Confirmed OpenClaw on Mac migrated and connected:
  - Gateway running on `127.0.0.1:18789`
  - RPC probe OK.

## Multi-server bot behavior work already shipped
- Multi-guild foundation migrated previously (M1..M9 chain) and active.
- Guild-scoped setup/jobs/finance/treasury/cashout/account paths were implemented.
- Startup/setup guardrails improved (live/config guild mismatch warning).

## Key behavior fixes made during this session
1. **Slash command sync issue in newly invited servers**
   - Fixed so commands sync to all connected guilds and on guild join.

2. **Setup restart wording for hosted users**
   - Updated text so hosted users are not told to run `systemctl`.

3. **Job rewards vs treasury model**
   - Changed normal job posting so rewards are treated as Org Points attribution,
     not treasury-reserved funds.
   - Share cashout/treasury aUEC behavior remains intact.

4. **Jobs routing after `/setup` changes**
   - Latest fix: jobs routing now reads guild settings live from DB
     (`JOB_CATEGORY_CHANNEL_MAP`, `JOBS_CHANNEL_ID`) at request time.
   - Result: no restart required after setup/channel remap.

## Docs / public-private policy state
- Public docs were cleaned to hosted usage flow (no self-host install steps in docs pages).
- Private repo remains source for multi-server-sensitive bot code changes.
- Public repo should stay docs-safe unless explicitly approved for code push.

## Operational notes
- If jobs route incorrectly after channel/category edits:
  - Run `/setup start`, `/setup status`, then test `/jobs post`.
  - With latest routing fix, restart should not be needed.

- If slash commands missing in a new server:
  - Wait 30–120s, verify app command permissions, then retest.

## Access reminders (from TOOLS)
- AWS host: `13.60.18.89`
- User: `ubuntu`
- Key path (Mac): `~/Documents/clawdbot.pem`
- Repo on AWS: `/home/ubuntu/.openclaw/workspace/StarCitizen-Discord-OrgBot`
- Service: `starcitizen-orgbot.service`

## Post-upgrade reminder (Mac): keep machine awake for always-on bot
After macOS reinstall/migration, run this once:

```bash
mkdir -p ~/Library/LaunchAgents && cat > ~/Library/LaunchAgents/local.caffeinate.plist <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>local.caffeinate</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/caffeinate</string>
    <string>-dimsu</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
</dict>
</plist>
PLIST
launchctl unload ~/Library/LaunchAgents/local.caffeinate.plist 2>/dev/null || true
launchctl load ~/Library/LaunchAgents/local.caffeinate.plist
launchctl list | grep local.caffeinate || true
pgrep -fl "caffeinate -dimsu" || true
```

Disable later if needed:

```bash
launchctl unload ~/Library/LaunchAgents/local.caffeinate.plist
```

---
If continuity looks odd on Mac, use this file first before re-triaging.
