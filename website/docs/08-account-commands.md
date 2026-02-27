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

## Stock commands (user)

### `/stock buy stocks:<amount>`
Buys stocks at current market price.

### `/stock sell stocks:<amount>`
Creates a cashout request and locks those stocks until finance/admin handles it.

### `/stock portfolio`
Shows your stock holdings (total/available/locked) and valuation context.

### `/stock market`
Shows current stock market snapshot (price, change/trend context, demand metrics).

### `/stock price_nudge bps:<value>`
**Who:** finance/admin

Nudges stock price by bounded basis points.

### `/stock price_set price:<aUEC>`
**Who:** finance/admin

Sets stock price directly (bounded by config limits).

## Bonds

### `/bond redeem`
Redeems as much pending bond value as treasury can currently cover.

- Manual redemption by design (no auto-redeem)
- Remaining bond value stays pending when treasury is short
