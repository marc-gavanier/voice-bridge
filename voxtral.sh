#!/usr/bin/env bash
set -euo pipefail
unit=pont-vocal-voxtral
case "${1:-}" in
  start)
    systemd-run --user --unit="$unit" --collect \
      --setenv=VLLM_USE_FLASHINFER_SAMPLER=0 \
      --setenv=PATH="$PATH" \
      uv run --no-project --python 3.12 \
        --with "vllm==0.32.0" --with "vllm-omni==0.32.0" --with "mistral-common[audio]" \
        vllm serve mistralai/Voxtral-4B-TTS-2603 --omni --host 127.0.0.1 --port 8123
    ;;
  stop) systemctl --user stop "$unit" ;;
  status) systemctl --user --no-pager status "$unit" ;;
  logs) journalctl --user -u "$unit" -n 40 --no-pager ;;
  *) echo "usage: $0 start|stop|status|logs" >&2; exit 2 ;;
esac
