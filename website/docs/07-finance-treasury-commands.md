# 07 - Finance & Treasury Commands

## Finance commands

### `/finance pending_cashouts`
Shows pending/approved stock cashout queue.

### `/finance recent_payouts`
Shows recent payout and rep transactions.

### `/finance cashout_lookup request_id:<id>`
Shows a specific stock cashout request.

### `/finance user_audit user:<member>`
Shows recent user transactions and audit context.

### `/finance cashout_stats`
Shows cashout status counts + treasury snapshot + bond liability context.

### `/finance stock_stats`
Shows stock market visibility:
- current stock price
- change since open
- 7d trend
- net flow (since reset)
- total stocks + notional value
- treasury exposure

### `/finance reconcile`
Compares current treasury value against ledger-derived value.

---

## Treasury commands

### `/treasury status`
Shows:
- treasury amount
- outstanding bonds (liability)
- net available after bonds

### `/treasury set amount:<aUEC>`
**Who:** finance/admin

Sets treasury value directly and records baseline for reconcile workflows.

---

## Bond payout behavior (important)
When treasury cannot fully cover confirmed job payout:
- available amount is paid now
- remaining amount is issued as pending bonds
- users redeem pending bonds with `/bond redeem` when treasury has funds