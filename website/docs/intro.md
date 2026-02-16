# 01 - Startup Information

## Links
- Docs: https://sielski666.github.io/StarCitizen-Discord-OrgBot/
- Discord: https://discord.gg/BT8rpuX8R

## Start here
For hosted multi-server usage, server admins only need to:
1. Run `/setup start`
2. Run `/setup status`

## First operational flow
1. Create event template: `/eventtemplate add`
2. Post event job: `/eventjob post template:<name>`
3. RSVP participants via linked Discord Scheduled Event
4. Admin marks complete, then finance/admin confirms with `/jobs confirm`
5. Run `/finance reconcile`

## Non-event flow quick test
1. Run `/jobs post`
2. Choose area then tier
3. Submit modal
4. Confirm job routes to expected area channel
