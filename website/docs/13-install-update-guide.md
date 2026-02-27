# 01 - Hosted Server Setup Guide

This documentation set is focused on **hosted bot usage**.

If you are running your own deployment, keep self-host/install/update instructions in the public GitHub README.

## What server admins should do

### 1) Invite the bot
<<<<<<< HEAD
Use this invite link:
https://discord.com/oauth2/authorize?client_id=493717180584689665&scope=bot%20applications.commands&permissions=8
=======
Use the official invite link provided by the bot operator.
>>>>>>> a672f116b5385f07234b5109f7c5304b2f702b7c

### 2) Run setup in your server
- `/setup start`
- `/setup status`

### 3) Verify channels/roles
Confirm setup created or mapped the required channels and roles for your guild.

### 4) Validate core flow
- Post one normal job
- Post one event job
- Confirm finance/account commands respond as expected

## Multi-server smoke checklist
If you run the bot in multiple Discord servers, run this in each server:
1. `/setup start`
2. `/setup status` (verify guild live/config values)
3. Post one normal job and complete/confirm it
4. Post one event job, RSVP, lock attendance, confirm payout
5. Run `/finance reconcile`
