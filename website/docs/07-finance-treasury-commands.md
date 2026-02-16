# 07 - Finance & Treasury Commands

## Finance commands

### `/finance pending_cashouts`
Shows pending/approved cashout queue.

### `/finance recent_payouts`
Shows recent payout and rep transactions.

### `/finance cashout_lookup request_id:<id>`
Shows a specific cashout request.

### `/finance user_audit user:<member>`
Shows recent user transactions and audit context.

### `/finance cashout_stats`
Shows quick status counts and treasury snapshot.

### `/finance reconcile`
Compares current treasury value against ledger-derived value.
Use this after high transaction periods.

---

## Treasury commands

### `/treasury status`
Shows current treasury amount.

### `/treasury set amount:<aUEC>`
**Who:** finance/admin

Sets treasury value directly and records baseline for reconcile workflows.

---

## Escrow behavior (important)
- Job post reserves escrow from available treasury.
- Job confirm releases escrow into settled payout path.
- Job cancel releases escrow back to treasury available.
