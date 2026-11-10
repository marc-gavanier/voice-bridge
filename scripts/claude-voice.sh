#!/usr/bin/env bash
set -euo pipefail
project="$(cd "$(dirname "$0")/.." && pwd)"
voxtral="${VOICE_BRIDGE_VOXTRAL__URL:-http://127.0.0.1:8123}"
if ! curl --silent --fail --max-time 2 "$voxtral/health" >/dev/null; then
  "$project/scripts/voxtral.sh" start
  echo "Voxtral is starting, it takes about two and a half minutes." >&2
fi
config="$(jq --null-input --arg project "$project" '{
  mcpServers: {
    voice: {
      command: ($project + "/scripts/with-cuda.sh"),
      args: ["uv", "run", "--project", $project, "--frozen", "--quiet", "voice-bridge-channel"],
      alwaysLoad: true
    }
  }
}')"
exec claude --mcp-config "$config" --allowedTools mcp__voice__reply --dangerously-load-development-channels server:voice "$@"
