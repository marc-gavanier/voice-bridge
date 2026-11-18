#!/usr/bin/env bash
set -euo pipefail
unit=voice-bridge-voxtral
host=127.0.0.1
port=8123
ready_within=600
health_every=1
health_timeout=2
case "${1:-}" in
  start)
    case "$(systemctl --user is-active "$unit" || true)" in
      active) exit 0 ;;
      activating) exec systemctl --user start "$unit" ;;
    esac
    systemd-run --user --unit="$unit" --collect \
      --property=Type=exec \
      --property=TimeoutStartSec="$ready_within" \
      --property=ExecStartPost="curl --silent --fail --output /dev/null --retry-connrefused --retry-all-errors --retry $ready_within --retry-delay $health_every --retry-max-time $ready_within --max-time $health_timeout http://$host:$port/health" \
      --setenv=VLLM_USE_FLASHINFER_SAMPLER=0 \
      --setenv=PATH="$PATH" \
      uv run --no-project --python 3.12 \
        --with "vllm==0.32.0" --with "vllm-omni==0.32.0" --with "mistral-common[audio]" \
        vllm serve mistralai/Voxtral-4B-TTS-2603 --omni --host "$host" --port "$port"
    ;;
  stop) systemctl --user stop "$unit" ;;
  status) systemctl --user --no-pager status "$unit" ;;
  logs) journalctl --user -u "$unit" -n 40 --no-pager ;;
  *) echo "usage: $0 start|stop|status|logs" >&2; exit 2 ;;
esac
