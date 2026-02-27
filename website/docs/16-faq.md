# 16 - FAQ

## Do I need to fill every `.env` value manually?
No. Set essentials first (`DISCORD_TOKEN`, `GUILD_ID`) then run `/setup start`. It provisions most defaults.

## Who can run finance commands?
Finance/Admin roles only (depends on your role config).

## Why can’t users post event template jobs?
They need Event Handler (or Admin), and `EVENT_HANDLER_ROLE_ID` must be valid.

## Why is RSVP attendance different from what bot shows?
Attendance may be stale or locked. Run unlock -> sync -> lock and re-check.

## Can I run this on multiple servers?
Yes, but use clear per-server config and follow the multi-server ops guide.

## How do I test safely before go-live?
Use a staging Discord server and run:
1. `/setup start`
2. event template flow
3. non-event job flow
4. finance reconcile check

## What’s the fastest way to recover from broken setup?
1. `/setup doctor`
2. `/setup createchannels`
3. `/setup status`
4. restart bot if needed

## Is this bot safe to run with real treasury values?
Yes, if roles are correctly restricted and `.env` is private. Rotate tokens immediately if exposed.
