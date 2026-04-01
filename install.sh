#!/usr/bin/env bash
# install.sh — Linux / macOS setup script for Job-Profiler-Tool
# Usage: bash install.sh
set -euo pipefail

echo "=== Job-Profiler-Tool Setup ==="
echo ""
echo "This script will:"
echo "  1. Install uv (Python package manager) if not already present"
echo "  2. Sync project dependencies via uv"
echo ""
read -rp "Do you want to proceed? [Y/n] " confirm
if [[ -n "$confirm" && ! "$confirm" =~ ^[Yy]([Ee][Ss])?$ ]]; then
    echo "Aborted."
    exit 0
fi
echo ""

# ── Configuration ────────────────────────────────────────────────────────────
# SHA-256 hash of the uv install script — update when upgrading uv.
# If the hash no longer matches after an upstream release, update UV_INSTALL_HASH
# to the new value (after auditing the installer), or the pip3 fallback will be used.
UV_INSTALL_URL="https://astral.sh/uv/install.sh"
UV_INSTALL_HASH="B953B3F2A2764CBF860EEE4578A5949FA90ED010644C6BE1006F29010BADA946"

# 1. Install uv if not already available — download, verify hash, then execute
if ! command -v uv &>/dev/null; then
    echo "Installing uv..."

    tmp_installer="$(mktemp)"
    curl -LsSf "$UV_INSTALL_URL" -o "$tmp_installer" || {
        echo "ERROR: Failed to download uv installer."
        rm -f "$tmp_installer"
        exit 1
    }

    # Verify SHA-256 hash before execution
    if command -v sha256sum &>/dev/null; then
        actual_hash=$(sha256sum "$tmp_installer" | awk '{print $1}')
    elif command -v shasum &>/dev/null; then
        actual_hash=$(shasum -a 256 "$tmp_installer" | awk '{print $1}')
    else
        echo "ERROR: No sha256sum or shasum found — cannot verify installer."
        rm -f "$tmp_installer"
        exit 1
    fi

    if [[ "${actual_hash^^}" != "${UV_INSTALL_HASH^^}" ]]; then
        echo "WARNING: SHA-256 hash mismatch — the upstream uv installer may have been updated."
        echo "  Expected: $UV_INSTALL_HASH"
        echo "  Actual:   $actual_hash"
        echo "  Tip: update UV_INSTALL_HASH in this script to '${actual_hash^^}' after auditing the new installer."
        rm -f "$tmp_installer"
        # Fallback: install uv via pip3
        if command -v pip3 &>/dev/null; then
            echo "Attempting fallback: pip3 install uv ..."
            pip3 install --quiet uv || { echo "ERROR: pip3 fallback failed. Install uv manually: https://docs.astral.sh/uv/"; exit 1; }
        else
            echo "ERROR: pip3 not found. Install uv manually: https://docs.astral.sh/uv/"
            exit 1
        fi
    else
        echo "Hash verified."
        bash "$tmp_installer"
        rm -f "$tmp_installer"
        # Source the env file uv's installer creates, or add cargo/bin to PATH
        if [ -f "$HOME/.local/bin/env" ]; then
            # shellcheck disable=SC1091
            . "$HOME/.local/bin/env"
        else
            export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
        fi
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
echo "Running uv sync..."
uv sync
echo "uv sync succeeded."

echo ""
echo "=== Setup complete! ==="
echo "Activate the virtual environment with:"
echo "  source .venv/bin/activate"
echo "Then run the tool with:"
echo "  uv run main.py run"
