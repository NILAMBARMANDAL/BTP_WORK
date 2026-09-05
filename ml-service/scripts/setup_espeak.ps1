# Fetches espeak-ng for Windows without requiring admin rights or an
# installer UI. espeak-ng only ships an .msi for Windows (no portable zip),
# and a normal `msiexec /i` install requires admin + writes to Program Files.
# `msiexec /a` performs an "administrative install" — it just extracts the
# MSI's file table to a target directory, which does not require elevation.
# See GPU_SETUP.md / phonetics/README.md for why this matters (real Bengali
# G2P via espeak-ng, replacing/supplementing the ITRANS+Levenshtein heuristic).
#
# On Linux (Docker/institute server), don't run this — just
# `apt-get install espeak-ng` (see docker/ml-service.Dockerfile).
#
# Usage: powershell -File scripts/setup_espeak.ps1

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$vendorDir = Join-Path (Split-Path -Parent $here) "vendor"
$msiPath = Join-Path $vendorDir "espeak-ng.msi"
$targetDir = Join-Path $vendorDir "espeak-ng-extracted"

New-Item -ItemType Directory -Force -Path $vendorDir | Out-Null

if (-not (Test-Path $msiPath)) {
    Write-Output "Downloading espeak-ng.msi..."
    Invoke-WebRequest -Uri "https://github.com/espeak-ng/espeak-ng/releases/download/1.52.0/espeak-ng.msi" -OutFile $msiPath
}

if (-not (Test-Path (Join-Path $targetDir "eSpeak NG\espeak-ng.exe"))) {
    Write-Output "Extracting (admin-free administrative install)..."
    $proc = Start-Process msiexec.exe -ArgumentList "/a", "`"$msiPath`"", "/qn", "TARGETDIR=`"$targetDir`"" -Wait -PassThru -NoNewWindow
    if ($proc.ExitCode -ne 0) {
        throw "msiexec extraction failed with exit code $($proc.ExitCode)"
    }
}

$exe = Join-Path $targetDir "eSpeak NG\espeak-ng.exe"
if (Test-Path $exe) {
    Write-Output "espeak-ng ready at: $exe"
    Write-Output "Set ESPEAK_NG_EXE and ESPEAK_NG_DATA_PATH in .env to these paths (see .env.example)."
} else {
    throw "Extraction completed but espeak-ng.exe not found at expected path: $exe"
}
