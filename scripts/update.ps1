# StarCitizen Discord Org Bot safe updater (Windows)
# - Fetches latest changes from origin/main
# - Updates Python dependencies
# - Compiles key modules for quick syntax check
# - Optionally restarts a Windows service
# - Rolls back to previous commit if update fails

param(
  [string]$Branch = "main",
  [string]$ServiceName = "starcitizen-orgbot",
  [switch]$SkipServiceRestart
)

$ErrorActionPreference = "Stop"

$RootDir = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RootDir

if (-not (Test-Path ".git")) {
  Write-Error "This updater requires a git-based install (.git folder not found)."
}

$CurrentCommit = (git rev-parse HEAD).Trim()
Write-Host "[INFO] Current commit: $CurrentCommit"

Write-Host "[INFO] Fetching latest from origin/$Branch ..."
git fetch origin $Branch | Out-Host
$TargetCommit = (git rev-parse "origin/$Branch").Trim()

if ($CurrentCommit -eq $TargetCommit) {
  Write-Host "[OK] Already up to date."
  exit 0
}

Write-Host "[INFO] Updating to: $TargetCommit"

$rollback = {
  param($fromCommit, $serviceName, $skipRestart)
  Write-Warning "Update failed. Rolling back to $fromCommit"
  git reset --hard $fromCommit | Out-Host

  if (Test-Path ".venv\Scripts\pip.exe") {
    try { .\.venv\Scripts\pip.exe install -r requirements.txt | Out-Host } catch {}
  }

  if (-not $skipRestart) {
    try {
      if (Get-Service -Name $serviceName -ErrorAction SilentlyContinue) {
        Restart-Service -Name $serviceName -Force
        Write-Host "[WARN] Rolled back and restarted service '$serviceName'."
      }
    } catch {}
  }
}

try {
  git merge --ff-only "origin/$Branch" | Out-Host

  if (Test-Path ".venv\Scripts\pip.exe") {
    Write-Host "[INFO] Installing/updating dependencies in .venv ..."
    .\.venv\Scripts\pip.exe install -r requirements.txt | Out-Host
  } else {
    Write-Warning ".venv\Scripts\pip.exe not found, skipping dependency install."
  }

  Write-Host "[INFO] Running compile check ..."
  if (Test-Path ".venv\Scripts\python.exe") {
    .\.venv\Scripts\python.exe -m compileall -q bot.py cogs services
  } else {
    python -m compileall -q bot.py cogs services
  }

  if (-not $SkipServiceRestart) {
    if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
      Write-Host "[INFO] Restarting service: $ServiceName"
      Restart-Service -Name $ServiceName -Force
      Get-Service -Name $ServiceName | Format-Table -AutoSize | Out-Host
    } else {
      Write-Warning "Service '$ServiceName' not found. If you run manually, restart the bot process yourself."
    }
  }

  Write-Host "[OK] Update successful: $CurrentCommit -> $TargetCommit"
}
catch {
  & $rollback $CurrentCommit $ServiceName $SkipServiceRestart
  throw
}
