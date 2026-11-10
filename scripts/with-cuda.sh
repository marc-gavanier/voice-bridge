#!/usr/bin/env bash
set -euo pipefail
project="$(cd "$(dirname "$0")/.." && pwd)"
libraries="$(uv run --project "$project" --frozen --quiet python -c 'import nvidia.cublas, nvidia.cudnn; print(":".join(f"{next(iter(module.__path__))}/lib" for module in (nvidia.cublas, nvidia.cudnn)))')"
export LD_LIBRARY_PATH="$libraries${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$@"
