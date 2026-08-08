#!/bin/bash
echo "Starting interactive LinkedIn authentication via Playwright/VNC..."
echo "Make sure you have http://localhost:3000/ open (Live Debugger)!"
cd "$(dirname "$0")/.." || exit 1
CDP_URL="ws://localhost:3000" uv run python src/ljpa_reworked/auth/login_harness.py
