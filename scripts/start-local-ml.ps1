<#
.SYNOPSIS
    Starts the ml-service (FastAPI/Whisper) locally and exposes it over a
    free Cloudflare Quick Tunnel, for use as the public ML backend by the
    Render Node/Express service (ARCHITECTURE.md "Local ML hosting + tunnel").

.DESCRIPTION
    1. Verifies the uv environment is set up.
    2. Starts `uvicorn api.main:app` (ml-service) in the background.
    3. Waits for its local /health to respond.
    4. Starts `tools/cloudflared.exe tunnel --url http://127.0.0.1:<port>`
       (a free "Quick Tunnel" — no Cloudflare account, no domain needed).
    5. Parses the public https://*.trycloudflare.com URL from cloudflared's
       own output and health-checks it.
    6. Prints the URL to set as ML_SERVICE_URL on the Render backend.

    IMPORTANT — Quick Tunnel limitations (documented honestly, not hidden):
    - The URL is randomly generated EACH time this script runs. It is NOT
      stable across restarts. Whenever you restart this script, you must
      update ML_SERVICE_URL in the Render dashboard to the new URL.
    - This laptop must stay on, this FastAPI process must keep running, and
      this tunnel process must keep running for the public app to work.
      Closing this PowerShell window (or sleep/hibernate) takes the ML
      service offline from the public app's perspective.
    - For a stable hostname you would need a named Cloudflare Tunnel bound
      to a domain you own (a different, slightly more involved setup) —
      out of scope for this temporary/free local-hosting arrangement.

.PARAMETER Port
    Local port for FastAPI/uvicorn. Default 8000.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\start-local-ml.ps1
#>
param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

Write-Host "=== BTP local ML host + tunnel ===" -ForegroundColor Cyan

# --- 1. Verify environment -------------------------------------------------
$cloudflaredPath = Join-Path $repoRoot "tools\cloudflared.exe"
if (-not (Test-Path $cloudflaredPath)) {
    Write-Error "tools\cloudflared.exe not found. Download it first:`n  curl -L -o tools\cloudflared.exe https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
    exit 1
}

$uvCmd = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uvCmd) {
    Write-Error "uv is not on PATH. Install it first (see GPU_SETUP.md)."
    exit 1
}

Write-Host "Checking GPU (informational only -- WHISPER_DEVICE in .env decides what's actually used)..." -ForegroundColor DarkGray
try { nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader } catch { Write-Host "  nvidia-smi not available / no NVIDIA GPU detected." -ForegroundColor Yellow }

# --- 2. Start FastAPI/uvicorn in the background ----------------------------
$logDir = Join-Path $repoRoot "storage\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$mlLog = Join-Path $logDir "ml-service.log"

Write-Host "Starting ml-service on 127.0.0.1:$Port (uv run uvicorn)... log: $mlLog" -ForegroundColor Cyan
$mlProcess = Start-Process -FilePath "uv" `
    -ArgumentList "run", "--directory", "ml-service", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "$Port" `
    -WorkingDirectory $repoRoot `
    -RedirectStandardOutput $mlLog `
    -RedirectStandardError "$mlLog.err" `
    -PassThru -WindowStyle Hidden

Write-Host "ml-service PID: $($mlProcess.Id)"

# --- 3. Wait for local health -----------------------------------------------
$healthUrl = "http://127.0.0.1:$Port/health"
$maxWaitSec = 120
$elapsed = 0
$ok = $false
Write-Host "Waiting for ml-service to become healthy (model loads lazily, so this should be quick; up to ${maxWaitSec}s)..." -ForegroundColor Cyan
while ($elapsed -lt $maxWaitSec) {
    try {
        $resp = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 5
        if ($resp.StatusCode -eq 200) { $ok = $true; break }
    } catch {}
    Start-Sleep -Seconds 3
    $elapsed += 3
}

if (-not $ok) {
    Write-Error "ml-service did not become healthy within ${maxWaitSec}s. Check $mlLog / $mlLog.err"
    Write-Host "Stopping ml-service process $($mlProcess.Id)..."
    Stop-Process -Id $mlProcess.Id -Force -ErrorAction SilentlyContinue
    exit 1
}
Write-Host "ml-service is healthy at $healthUrl" -ForegroundColor Green

# --- 4. Start cloudflared Quick Tunnel -------------------------------------
$tunnelLog = Join-Path $logDir "cloudflared.log"
Write-Host "Starting Cloudflare Quick Tunnel (free, no account needed)... log: $tunnelLog" -ForegroundColor Cyan
$tunnelProcess = Start-Process -FilePath $cloudflaredPath `
    -ArgumentList "tunnel", "--url", "http://127.0.0.1:$Port" `
    -WorkingDirectory $repoRoot `
    -RedirectStandardOutput $tunnelLog `
    -RedirectStandardError "$tunnelLog.err" `
    -PassThru -WindowStyle Hidden

Write-Host "cloudflared PID: $($tunnelProcess.Id)"

# --- 5. Parse the public URL out of cloudflared's stderr log --------------
$publicUrl = $null
$maxWaitSec = 30
$elapsed = 0
while ($elapsed -lt $maxWaitSec -and -not $publicUrl) {
    Start-Sleep -Seconds 2
    $elapsed += 2
    if (Test-Path "$tunnelLog.err") {
        $match = Select-String -Path "$tunnelLog.err" -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($match) { $publicUrl = $match.Matches[0].Value }
    }
}

if (-not $publicUrl) {
    Write-Error "Could not find the tunnel URL in $tunnelLog.err within ${maxWaitSec}s -- inspect that file manually."
    exit 1
}

Write-Host ""
Write-Host "=== Public ML service URL (set this as ML_SERVICE_URL on the Render backend) ===" -ForegroundColor Green
Write-Host $publicUrl -ForegroundColor Yellow
Write-Host ""

# --- 6. Health-check the public URL ----------------------------------------
Write-Host "Verifying the tunnel actually serves /health..." -ForegroundColor Cyan
Start-Sleep -Seconds 2
try {
    $pubResp = Invoke-WebRequest -Uri "$publicUrl/health" -UseBasicParsing -TimeoutSec 15
    Write-Host "Public /health -> HTTP $($pubResp.StatusCode): $($pubResp.Content)" -ForegroundColor Green
} catch {
    Write-Host "Public health check failed: $_" -ForegroundColor Red
    Write-Host "The tunnel process may still be starting -- retry manually: curl $publicUrl/health" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "ml-service PID=$($mlProcess.Id), cloudflared PID=$($tunnelProcess.Id)." -ForegroundColor DarkGray
Write-Host "To stop everything: Stop-Process -Id $($mlProcess.Id),$($tunnelProcess.Id) -Force" -ForegroundColor DarkGray
Write-Host "Reminder: this URL is a Quick Tunnel -- it changes every time this script restarts." -ForegroundColor DarkGray
