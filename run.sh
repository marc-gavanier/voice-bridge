#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
site="$(uv run -q python -c 'import site; print(site.getsitepackages()[0])')"
export LD_LIBRARY_PATH="$site/nvidia/cublas/lib:$site/nvidia/cudnn/lib:${LD_LIBRARY_PATH:-}"
exec uv run -q python -W ignore "$@"
