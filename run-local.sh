#!/bin/sh
set -eu
cd "$(dirname "$0")"
python3 scripts/bootstrap.py
UV_CACHE_DIR=.uv-cache uv sync --frozen
docker compose --env-file .local/compose.env up -d --wait db
if [ ! -f frontend/dist/index.html ]; then
  (cd frontend && npm ci && npm run build)
fi
export PYTHONPATH=src
.venv/bin/python -m veriforge.db
.venv/bin/python -m veriforge.worker &
worker_pid=$!
.venv/bin/python -m veriforge.monitor &
monitor_pid=$!
trap 'kill "$worker_pid" "$monitor_pid" 2>/dev/null || true' EXIT INT TERM
.venv/bin/uvicorn --app-dir src veriforge.api.app:app --host 127.0.0.1 --port 8123
