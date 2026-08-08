#!/bin/bash
echo "Starting interactive LinkedIn authentication via Playwright/VNC..."
echo "Make sure you have http://localhost:7900/vnc.html open!"
podman exec -it linkedin-bot uv run python /app/src/ljpa_reworked/auth/login_harness.py
