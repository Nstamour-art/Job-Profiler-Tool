#!/usr/bin/env pwsh
# install.ps1 — Windows setup script for Job-Profiler-Tool
# Usage: powershell -ExecutionPolicy ByPass -File install.ps1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "=== Job-Profiler-Tool Setup ===" -ForegroundColor Cyan

# 1. Install uv if not already available
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Installing uv..." -ForegroundColor Yellow
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    # Refresh PATH so uv is available in this session
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "User") + ";" + $env:PATH
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Host "ERROR: uv installation failed or is not on PATH." -ForegroundColor Red
        Write-Host "Please restart your terminal and re-run this script." -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "uv is already installed." -ForegroundColor Green
}

# 2. Sync project (creates .venv and installs dependencies)
#    --inexact: don't remove packages uv didn't install (avoids RECORD conflicts with pip)
Write-Host "Running uv sync..." -ForegroundColor Yellow
uv sync --inexact
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: uv sync failed." -ForegroundColor Red
    exit 1
}
Write-Host "uv sync succeeded." -ForegroundColor Green

# 3. Install hindsight via uv run pip (uv pip fails on legacy use_2to3 builds)
Write-Host "Installing hindsight>=0.1.7..." -ForegroundColor Yellow
uv run pip install "hindsight>=0.1.7"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: hindsight installation failed." -ForegroundColor Red
    exit 1
}
Write-Host "hindsight installed." -ForegroundColor Green

Write-Host ""
Write-Host "=== Setup complete! ===" -ForegroundColor Cyan
Write-Host "Activate the virtual environment with:"
Write-Host "  .\.venv\Scripts\Activate.ps1" -ForegroundColor White
