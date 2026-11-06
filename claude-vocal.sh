#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
curl -sf -m 2 http://127.0.0.1:8123/health >/dev/null || { "$here/voxtral.sh" start; echo "Voxtral démarre, environ 2 min 30." >&2; }
exec claude --mcp-config "$here/mcp.json" --append-system-prompt "$(cat "$here/consignes-vocales.txt")" --allowedTools mcp__voix__reply --dangerously-load-development-channels server:voix "$@"
