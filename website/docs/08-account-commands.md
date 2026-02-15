# 09 - Account Commands

## `/account overview`
Shows:
- Org Credits
- Shares
- Reputation
- Level
- Tier

## `/account buyshares amount:<n>`
Buys shares using available Org Credits.

## `/account sellshares amount:<n>`
Creates cashout request and locks shares until approved/rejected.

## `/account debugtiers user:<member>`
**Who:** finance/admin

Audits user level/tier and expected role mapping.

## `/account rolesync [user:<member>]`
**Who:** finance/admin

Syncs tier role assignment to match current level.
- With user arg: sync one user.
- Without user arg: broader sync behavior per implementation.
