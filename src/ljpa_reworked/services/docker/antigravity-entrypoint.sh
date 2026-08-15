#!/bin/sh
set -eu

mkdir -p /runtime/harness-scraper /runtime/workspace /runtime/gemini/config /home/agent/.imap-mcp
if [ ! -f /home/agent/.imap-mcp/accounts.json ]; then
  # ponytail: one read-only Gmail inbox; add a second account only when a distinct mailbox is needed.
  printf '%s\n' '[
  {
    "id": "ljpa-gmail",
    "name": "LJPA Gmail",
    "host": "imap.gmail.com",
    "port": 993,
    "user": "",
    "password": "",
    "tls": true,
    "email": ""
  }
]' > /home/agent/.imap-mcp/accounts.json
  chmod 600 /home/agent/.imap-mcp/accounts.json
fi
cp -an /home/agent/.gemini-default/. /runtime/gemini/
cp /home/agent/.gemini-default/config/mcp_config.json /runtime/gemini/config/mcp_config.json
cp /home/agent/.gemini-default/GEMINI.md /runtime/gemini/GEMINI.md
rm -rf /home/agent/.gemini
ln -s /runtime/gemini /home/agent/.gemini
cd /runtime/workspace
exec "$@"
