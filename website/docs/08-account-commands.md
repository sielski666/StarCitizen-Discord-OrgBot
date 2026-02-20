# 08 - Account Commands

## `/account overview`
Shows:
- account balance (aUEC)
- stocks (total / available / locked)
- pending stock sells
- estimated stock value
- reputation / level / tier
- pending bonds and outstanding bond value

## `/account debugtiers user:<member>`
**Who:** finance/admin

Audits user level/tier and expected role mapping.

## `/account rolesync [user:<member>]`
**Who:** finance/admin

Syncs tier role assignment to match current level.

---

## Stock trading moved out of `/account`
Use `/stock` commands instead:
- `/stock buy`
- `/stock sell`
- `/stock portfolio`
- `/stock market`
