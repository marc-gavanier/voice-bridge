#!/usr/bin/env bash
set -euo pipefail
project="$(cd "$(dirname "$0")/.." && pwd)"
voxtral="${VOICE_BRIDGE_VOXTRAL__URL:-http://127.0.0.1:8123}"
if ! curl --silent --fail --max-time 2 "$voxtral/health" >/dev/null; then
  "$project/scripts/voxtral.sh" start
  echo "Voxtral is starting, it takes about two and a half minutes." >&2
fi
config="${XDG_RUNTIME_DIR:-/tmp}/voice-bridge-mcp.json"
jq --null-input --arg project "$project" --arg pid "$$" '{
  mcpServers: {
    voice: {
      command: ($project + "/scripts/with-cuda.sh"),
      args: ["uv", "run", "--project", $project, "--frozen", "--quiet", "voice-bridge-channel"],
      env: {VOICE_BRIDGE_CLAUDE_PID: $pid},
      alwaysLoad: true
    }
  }
}' >"$config"
settings="${XDG_RUNTIME_DIR:-/tmp}/voice-bridge-settings.json"
jq --null-input --arg project "$project" '{
  hooks: {
    PreToolUse: [
      {
        matcher: "*",
        hooks: [
          {
            type: "command",
            command: ("uv run --project " + ($project | @sh) + " --frozen --quiet voice-bridge-stop-hook")
          }
        ]
      }
    ]
  }
}' >"$settings"
exec claude --mcp-config "$config" --settings "$settings" --allowedTools mcp__voice__reply mcp__voice__end_session --dangerously-load-development-channels server:voice "$@"
