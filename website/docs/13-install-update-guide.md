# 01 - Install & Update Guide

Use this page if you want the **auto-update command** (`./scripts/update.sh`).

## Two install methods (important)

### A) Git clone install (recommended)
- You install with `git clone`
- Repo has `.git` history
- You can update with one command: `./scripts/update.sh`
- Best for long-term/self-hosted usage

### B) Release ZIP/manual install
- You download source ZIP from GitHub releases/repo
- No `.git` folder/history
- `./scripts/update.sh` will **not** work
- You must manually replace files on each update

## Recommended install (supports auto-update)

### Linux / macOS

#### Step 1 — Clone repo
```bash
git clone https://github.com/sielski666/StarCitizen-Discord-OrgBot.git
cd StarCitizen-Discord-OrgBot
```

#### Step 2 — Create and activate virtualenv
```bash
python -m venv .venv
source .venv/bin/activate
```

#### Step 3 — Install dependencies
```bash
pip install -r requirements.txt
```

#### Step 4 — Configure environment
```bash
cp .env.example .env
```
Then edit `.env` and set at least:
- `DISCORD_TOKEN`
- required guild/role/channel IDs (or run `/setup start`)

#### Step 5 — Run bot
```bash
python bot.py
```

### Windows (PowerShell)

#### Step 1 — Clone repo
```powershell
git clone https://github.com/sielski666/StarCitizen-Discord-OrgBot.git
cd StarCitizen-Discord-OrgBot
```

#### Step 2 — Create and activate virtualenv
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

#### Step 3 — Install dependencies
```powershell
pip install -r requirements.txt
```

#### Step 4 — Configure environment
```powershell
Copy-Item .env.example .env
```
Then edit `.env` and set at least:
- `DISCORD_TOKEN`
- required guild/role/channel IDs (or run `/setup start`)

#### Step 5 — Run bot
```powershell
python bot.py
```

## Auto-update flow (git install only)

### Linux / macOS
From repo root:
```bash
./scripts/update.sh
```

### Windows
- Recommended: run the updater from **WSL** or **Git Bash**.
- Native PowerShell users should follow the manual update flow below.

What the updater script does:
1. fetches latest `origin/main`
2. fast-forwards local repo
3. updates dependencies
4. runs compile checks
5. restarts `starcitizen-orgbot`
6. rolls back to previous commit if update fails

## Manual update flow (ZIP/manual installs)

If you installed without git history:
1. Download latest release/source
2. Stop bot service/process
3. Replace project files
4. Reinstall dependencies (`pip install -r requirements.txt`)
5. Start/restart bot service

## Quick check after any update

### Linux (systemd)
```bash
sudo systemctl status starcitizen-orgbot --no-pager
```

### Windows (manual run)
- confirm the bot process is running in your terminal
- verify no startup errors in console output

And in Discord:
- run `/setup status`
- run one test job flow
