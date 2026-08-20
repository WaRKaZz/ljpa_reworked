#!/bin/sh
set -e

python3 << 'EOF'
import os, json, urllib.request, zipfile, re
key = os.getenv('CAPSOLVER_API_KEY', '').strip()
ext_dir = '/app/data/extensions/capsolver'
if key and not os.path.exists(f'{ext_dir}/manifest.json'):
    os.makedirs(ext_dir, exist_ok=True)
    url = 'https://github.com/CapSolver/capsolver-browser-extension/releases/download/v.1.17.0/CapSolver.Browser.Extension-chrome-v1.17.0.zip'
    zip_path = '/tmp/capsolver.zip'
    print(f'[init_cloak] Downloading CapSolver extension from {url}...')
    urllib.request.urlretrieve(url, zip_path)
    print(f'[init_cloak] Extracting CapSolver extension to {ext_dir}...')
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(ext_dir)
    os.remove(zip_path)

cfg_js = f"{ext_dir}/assets/config.js"
if key and os.path.exists(cfg_js):
    with open(cfg_js, "r") as f:
        content = f.read()
    content = re.sub(r"apiKey:\s*['\"].*?['\"]", f"apiKey: '{key}'", content)
    content = re.sub(r"useCapsolver:\s*(true|false)", "useCapsolver: true", content)
    with open(cfg_js, "w") as f:
        f.write(content)
    print("[init_cloak] CapSolver API Key successfully configured in config.js")
EOF

EXTRA_ARGS="--password-store=basic --use-mock-keychain --log-level=3"
if [ -d "/app/data/extensions/capsolver" ] && [ -f "/app/data/extensions/capsolver/manifest.json" ]; then
    EXTRA_ARGS="$EXTRA_ARGS --load-extension=/app/data/extensions/capsolver --disable-extensions-except=/app/data/extensions/capsolver"
fi

# Pre-warm Chrome instance in the background once cloakserve starts listening
(
    while ! curl -s http://127.0.0.1:9222/json/version >/dev/null 2>&1; do
        sleep 0.2
    done
    curl -s http://127.0.0.1:9222/json/list >/dev/null 2>&1 || true
) &

exec cloakserve --port=9222 --idle-timeout=0 $EXTRA_ARGS
