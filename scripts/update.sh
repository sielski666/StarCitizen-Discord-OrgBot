#!/usr/bin/env bash
set -euo pipefail

# StarCitizen Discord Org Bot safe updater
# - Fetches latest changes from origin/main
# - Updates Python dependencies
# - Compiles key modules for a quick syntax check
# - Restarts service
# - Rolls back to previous commit if update fails

SERVICE_NAME="starcitizen-orgbot"
BRANCH="main"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -d .git ]]; then
  echo "[ERROR] This updater requires a git-based install (.git folder not found)."
  exit 1
fi

CURRENT_COMMIT="$(git rev-parse HEAD)"
echo "[INFO] Current commit: $CURRENT_COMMIT"

echo "[INFO] Fetching latest from origin/$BRANCH ..."
git fetch origin "$BRANCH"
TARGET_COMMIT="$(git rev-parse "origin/$BRANCH")"

if [[ "$CURRENT_COMMIT" == "$TARGET_COMMIT" ]]; then
  echo "[OK] Already up to date."
  exit 0
fi

echo "[INFO] Updating to: $TARGET_COMMIT"

rollback() {
  echo "[WARN] Update failed. Rolling back to $CURRENT_COMMIT"
  git reset --hard "$CURRENT_COMMIT"
  if [[ -x .venv/bin/pip ]]; then
    .venv/bin/pip install -r requirements.txt >/dev/null 2>&1 || true
  fi
  sudo systemctl restart "$SERVICE_NAME" || true
  echo "[WARN] Rollback complete."
}
trap rollback ERR

# Fast-forward only to avoid accidental history rewrites on host
if ! git merge --ff-only "origin/$BRANCH"; then
  echo "[ERROR] Fast-forward merge failed. Resolve local changes first."
  exit 1
fi

if [[ -x .venv/bin/pip ]]; then
  echo "[INFO] Installing/updating dependencies in .venv ..."
  .venv/bin/pip install -r requirements.txt
else
  echo "[WARN] .venv/bin/pip not found, skipping dependency install."
fi

echo "[INFO] Running compile check ..."
if [[ -x .venv/bin/python ]]; then
  .venv/bin/python -m compileall -q bot.py cogs services
else
  python3 -m compileall -q bot.py cogs services
fi

echo "[INFO] Restarting service: $SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"
sudo systemctl status "$SERVICE_NAME" --no-pager | sed -n '1,12p'

trap - ERR
echo "[OK] Update successful: $CURRENT_COMMIT -> $TARGET_COMMIT"
