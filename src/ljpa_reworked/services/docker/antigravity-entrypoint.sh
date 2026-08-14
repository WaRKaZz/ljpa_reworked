#!/bin/sh
set -eu

mkdir -p /runtime/harness-scraper /runtime/workspace /runtime/gemini/config
cp -an /home/agent/.gemini-default/. /runtime/gemini/
cp /home/agent/.gemini-default/config/mcp_config.json /runtime/gemini/config/mcp_config.json
cp /home/agent/.gemini-default/GEMINI.md /runtime/gemini/GEMINI.md
rm -rf /home/agent/.gemini
ln -s /runtime/gemini /home/agent/.gemini
cd /runtime/workspace
exec "$@"
