# Finance & Reconcile

## Core commands
- `/finance reconcile`
- treasury and payout operations via finance/admin workflows

## Escrow model
- On job create: escrow reserved from available treasury
- On confirm: escrow released to settled/payout path
- On cancel: escrow released back to treasury available

## Ledger
Audit table includes treasury and event payout snapshot entries.
Use reconcile regularly after payout-heavy periods.
