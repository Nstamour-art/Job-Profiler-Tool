#!/usr/bin/env bash
# install.sh — Linux / macOS setup script for Job-Profiler-Tool
# Usage: bash install.sh
set -euo pipefail

echo "=== Job-Profiler-Tool Setup ==="

# Pin uv to a specific release so the install URL is immutable and reproducible.
# To upgrade uv: update UV_VERSION below, then re-run this script.
UV_VERSION="0.11.3"

# 1. Install uv if not already available
if ! command -v uv &>/dev/null; then
    echo "Installing uv ${UV_VERSION}..."
    curl -LsSf "https://astral.sh/uv/${UV_VERSION}/install.sh" | sh
    # Source the env file uv's installer creates, or add cargo/bin to PATH
    if [ -f "$HOME/.local/bin/env" ]; then
        # shellcheck disable=SC1091
        . "$HOME/.local/bin/env"
    else
        export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    fi
    if ! command -v uv &>/dev/null; then
        echo "ERROR: uv installation failed or is not on PATH."
        echo "Please restart your terminal and re-run this script."
        exit 1
    fi
else
    echo "uv is already installed."
fi

# 2. Sync project (creates .venv and installs dependencies)
#    --inexact: don't remove packages uv didn't install (avoids RECORD conflicts with pip)
echo "Running uv sync..."
uv sync --inexact
echo "uv sync succeeded."

# 3. Install hindsight via uv run pip (uv pip fails on legacy use_2to3 builds)
echo "Installing hindsight>=0.1.7..."
uv run pip install "hindsight>=0.1.7"
echo "hindsight installed."

echo ""
echo "=== Setup complete! ==="
echo "Activate the virtual environment with:"
echo "  source .venv/bin/activate"
