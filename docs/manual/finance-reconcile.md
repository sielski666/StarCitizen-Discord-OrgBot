# Finance & Reconcile

## Finance commands
- `/finance pending_cashouts`
- `/finance recent_payouts`
- `/finance cashout_lookup`
- `/finance user_audit`
- `/finance cashout_stats`
- `/finance reconcile`

## Treasury commands
- `/treasury status`
- `/treasury set amount:<aUEC>` (finance/admin)

## Escrow model (jobs)
- On create: reserves escrow from available treasury
- On confirm: releases escrow into settled payout path
- On cancel: releases escrow back to treasury available

## Ledger/audit
Ledger captures:
- treasury set operations
- escrow reserve/release entries
- event payout snapshot details (attendee split notes)

Use `/finance reconcile` after high-volume payout periods or treasury corrections.
