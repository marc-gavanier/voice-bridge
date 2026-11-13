#!/usr/bin/env bash
set -euo pipefail
project="$(cd "$(dirname "$0")/.." && pwd)"
voxtral="${VOICE_BRIDGE_SPEECH__URL:-http://127.0.0.1:8123}"
if ! curl --silent --fail --max-time 2 "$voxtral/health" >/dev/null; then
  "$project/scripts/voxtral.sh" start
  echo "Voxtral is starting, it takes about two and a half minutes." >&2
fi
environment_file="${XDG_CONFIG_HOME:-$HOME/.config}/voice-bridge/environment"
environment='{}'
if [[ -f "$environment_file" ]]; then
  environment="$(jq --raw-input --null-input '
    [inputs
      | select(test("^[A-Za-z_][A-Za-z0-9_]*="))
      | capture("^(?<key>[^=]+)=(?<value>.*)$")
      | {(.key): (.value | sub("^\"(?<inner>.*)\"$"; "\(.inner)"))}]
    | add // {}' "$environment_file")"
fi
config="${XDG_RUNTIME_DIR:-/tmp}/voice-bridge-mcp.json"
jq --null-input --arg project "$project" --arg pid "$$" --argjson environment "$environment" '
  ($environment | to_entries | any(
    ((.key | test("^OTEL_EXPORTER_OTLP_(TRACES_|METRICS_|LOGS_)?ENDPOINT$")) and .value != "")
    or ((.key | test("^OTEL_(TRACES|METRICS|LOGS)_EXPORTER$")) and .value != "" and .value != "none")
  )) as $otel
  | (($environment.SENTRY_DSN // "") != "") as $sentry
  | {
      mcpServers: {
        voice: {
          command: ($project + "/scripts/with-cuda.sh"),
          args: (["uv", "run", "--project", $project, "--frozen", "--quiet"]
            + (if $otel then ["--extra", "otel"] else [] end)
            + (if $sentry then ["--extra", "sentry"] else [] end)
            + (if $otel then ["opentelemetry-instrument"] else [] end)
            + ["voice-bridge-channel"]),
          env: ((if $otel then {OTEL_SERVICE_NAME: "voice-bridge"} else {} end) + $environment + {VOICE_BRIDGE_CLAUDE_PID: $pid}),
          alwaysLoad: true
        }
      }
    }' >"$config"
settings="${XDG_RUNTIME_DIR:-/tmp}/voice-bridge-settings.json"
jq --null-input --arg project "$project" '
  ("uv run --project " + ($project | @sh) + " --frozen --quiet ") as $run
  | [{hooks: [{type: "command", command: ($run + "voice-bridge-activity-hook"), async: true}]}] as $activity
  | {
      hooks: {
        PreToolUse: [
          {
            matcher: "*",
            hooks: [{type: "command", command: ($run + "voice-bridge-tool-hook")}]
          }
        ],
        UserPromptSubmit: $activity,
        Stop: $activity,
        StopFailure: $activity,
        SessionEnd: $activity,
        SubagentStart: $activity,
        SubagentStop: $activity
      }
    }' >"$settings"
exec claude --mcp-config "$config" --settings "$settings" --allowedTools mcp__voice__reply mcp__voice__end_session --dangerously-load-development-channels server:voice "$@"
