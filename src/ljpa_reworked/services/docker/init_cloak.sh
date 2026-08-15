#!/bin/sh
set -e

python3 -c "
import os, json, urllib.request, zipfile
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

if key and os.path.exists(f'{ext_dir}/assets/config.json'):
    cfg_path = f'{ext_dir}/assets/config.json'
    try:
        cfg = json.load(open(cfg_path))
    except Exception:
        cfg = {}
    cfg.update({
        'apiKey': key,
        'enabledForRecaptchaV2': True,
        'enabledForRecaptchaV3': True,
        'enabledForHCaptcha': True,
        'enabledForFunCaptcha': True,
        'enabledForCloudflare': True,
        'enabledForAwsClassification': True,
        'useCapSolverHost': True
    })
    json.dump(cfg, open(cfg_path, 'w'), indent=2)
    print('[init_cloak] CapSolver API Key successfully configured in config.json')
"

# Start dbus session if available to eliminate dbus connection warnings
if command -v dbus-daemon >/dev/null 2>&1; then
    mkdir -p /var/run/dbus
    dbus-daemon --system --fork 2>/dev/null || true
    eval "$(dbus-launch --sh-syntax 2>/dev/null || true)"
fi

EXTRA_ARGS="--password-store=basic --use-mock-keychain --log-level=3"
if [ -d "/app/data/extensions/capsolver" ] && [ -f "/app/data/extensions/capsolver/manifest.json" ]; then
    EXTRA_ARGS="$EXTRA_ARGS --load-extension=/app/data/extensions/capsolver --disable-extensions-except=/app/data/extensions/capsolver"
fi

exec cloakserve --host 0.0.0.0 --port 9222 --extra-args="$EXTRA_ARGS"
