#!/usr/bin/env bash
# NEXGRAFT AI launcher for Linux / macOS
set -euo pipefail
cd "$(dirname "$0")"

PY=${PYTHON:-python3}
if [ ! -x .venv/bin/python ]; then
  echo "[1/3] Creating Python virtual environment..."
  "$PY" -m venv .venv
fi
echo "[2/3] Checking Python packages..."
.venv/bin/python -m pip install --disable-pip-version-check -q -r backend/requirements.txt

if [ ! -f frontend/dist/index.html ]; then
  command -v npm >/dev/null || { echo "Node.js 20.19+ or 22+ is required once to build the interface: https://nodejs.org"; exit 1; }
  echo "[3/3] Building the web interface (first run only)..."
  (cd frontend && npm install && npm run build)
fi

[ -f .env ] || cp .env.example .env
exec .venv/bin/python run.py "$@"
