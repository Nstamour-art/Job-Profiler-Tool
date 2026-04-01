#!/usr/bin/env pwsh
# install.ps1 — Windows setup script for Job-Profiler-Tool
# Usage: powershell -ExecutionPolicy ByPass -File install.ps1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "=== Job-Profiler-Tool Setup ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "This script will:" -ForegroundColor White
Write-Host "  1. Install uv (Python package manager) if not already present" -ForegroundColor White
Write-Host "  2. Sync project dependencies via uv" -ForegroundColor White
Write-Host ""
$confirm = Read-Host "Do you want to proceed? [Y/n]"
if ($confirm -and $confirm -notin @('y','Y','yes','Yes','YES')) {
    Write-Host "Aborted." -ForegroundColor Yellow
    exit 0
}
Write-Host ""

# ── Configuration ────────────────────────────────────────────────────────────
# SHA-256 hash of the uv install script — update when upgrading uv.
# If the hash no longer matches after an upstream release, update UV_INSTALL_HASH
# to the new value (after auditing the installer), or the pip fallback will be used.
$UV_INSTALL_URL  = "https://astral.sh/uv/install.ps1"
$UV_INSTALL_HASH = "282D58C11A9C1E21E8C59C12DC0618D0E94A621526C8F814948777BA7D605335"

# 1. Install uv if not already available — download, verify hash, then execute
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Installing uv..." -ForegroundColor Yellow

    $tempInstaller = Join-Path ([System.IO.Path]::GetTempPath()) "uv_install.ps1"
    try {
        Invoke-WebRequest -Uri $UV_INSTALL_URL -OutFile $tempInstaller -UseBasicParsing
    } catch {
        Write-Host "ERROR: Failed to download uv installer: $_" -ForegroundColor Red
        exit 1
    }

    # Verify SHA-256 hash before execution
    $actualHash = (Get-FileHash -Path $tempInstaller -Algorithm SHA256).Hash
    if ($actualHash -ne $UV_INSTALL_HASH) {
        Write-Host "WARNING: SHA-256 hash mismatch — the upstream uv installer may have been updated." -ForegroundColor Yellow
        Write-Host "  Expected: $UV_INSTALL_HASH" -ForegroundColor Yellow
        Write-Host "  Actual:   $actualHash" -ForegroundColor Yellow
        Write-Host "  Tip: update UV_INSTALL_HASH in this script to '$actualHash' after auditing the new installer." -ForegroundColor Yellow
        Remove-Item -Force $tempInstaller
        # Fallback: install uv via pip
        Write-Host "Attempting fallback: pip install uv ..." -ForegroundColor Yellow
        $pipCmd = Get-Command pip -ErrorAction SilentlyContinue
        if ($pipCmd) {
            pip install --quiet uv
            if ($LASTEXITCODE -ne 0) {
                Write-Host "ERROR: pip fallback failed. Install uv manually: https://docs.astral.sh/uv/" -ForegroundColor Red
                exit 1
            }
        } else {
            Write-Host "ERROR: pip not found. Install uv manually: https://docs.astral.sh/uv/" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "Hash verified." -ForegroundColor Green

        powershell -ExecutionPolicy ByPass -File $tempInstaller
        Remove-Item -Force $tempInstaller
    }

    # Refresh PATH: add default uv install locations so uv is available in this session
    $uvDefaultDir = Join-Path $env:USERPROFILE ".local" "bin"
    $env:PATH = $uvDefaultDir + ";" + [System.Environment]::GetEnvironmentVariable("PATH", "User") + ";" + $env:PATH
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Host "ERROR: uv installation failed or is not on PATH." -ForegroundColor Red
        Write-Host "Please restart your terminal and re-run this script." -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "uv is already installed." -ForegroundColor Green
}

# 2. Sync project (creates .venv and installs dependencies)
uv sync
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: uv sync failed." -ForegroundColor Red
    exit 1
}
Write-Host "uv sync succeeded." -ForegroundColor Green

Write-Host ""
Write-Host "=== Setup complete! ===" -ForegroundColor Cyan
Write-Host "Activate the virtual environment with:"
Write-Host "  .\.venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host "Then run the tool with:"
Write-Host "  uv run main.py run" -ForegroundColor White
