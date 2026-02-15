# Setup

## Automated setup
Use `/setup start` (admin):
- ensures key channels (jobs/treasury/share-sell-confirm)
- ensures `Event Handler` role
- writes IDs into `.env`

Then restart service:
```bash
sudo systemctl restart starcitizen-orgbot
```

## Verify
Use `/setup status` and confirm all required fields are present.

## Role model
- Admin: full control
- Finance: confirm payouts, attendance lock/sync controls
- Jobs Admin: job admin operations
- Event Handler: allowed to post event templates
