---
id: multi-server-operations
title: "14 - Multi-Server Operations"
---

Use this page when running one bot across multiple Discord servers.

## Scope
This runbook covers:
- per-server setup
- tenant isolation checks
- operations and troubleshooting

This page intentionally does **not** cover install/update.

## Per-server onboarding checklist
Run these in each server (guild):
1. `/setup start`
2. `/setup status`
3. Confirm live/config guild values match
4. Confirm required roles/channels are present and correct

## Validation smoke flow (per server)
1. Post one normal job and run through completion
2. Post one event job from template
3. RSVP 1+ participants
4. Lock attendance
5. Confirm payout
6. Run `/finance reconcile`
7. Run `/finance recent_payouts`
8. Run `/finance user_audit` for one member
9. Run `/account overview` for at least one member

## Isolation expectations
When scoped correctly, each server should only see its own:
- jobs
- event attendance data
- treasury values
- payout/rep transaction history
- cashout request handling
- account balances/shares/rep

## Common operator mistakes
- Running `/setup start` in one server and assuming all servers are configured
- Reusing wrong channel/role IDs between servers
- Skipping `/setup status` verification in each server
- Testing only jobs but not account/finance views

## Fast troubleshooting
### Guild mismatch warning in setup status
- Re-run `/setup start` in that server
- Re-check `/setup status`

### Missing data in a server
- Confirm setup was completed in that server
- Run a small transaction/job and re-check `/account overview`
- Run `/finance recent_payouts` to verify guild-scoped entries

### Suspected cross-server bleed
- Compare `/finance user_audit` for same user in two servers
- If results overlap unexpectedly, pause changes and capture command outputs for triage

## Recommended rollout sequence
1. Configure Server A and validate full smoke flow
2. Configure Server B and validate full smoke flow
3. Repeat for remaining servers
4. Only then announce multi-server production readiness
