#!/usr/bin/env bash
# Fine-tunes Qwen for the Bioinformatics and Hardware Design workspaces (see docs/FINETUNING.md).
set -euo pipefail
cd "$(dirname "$0")"

command -v nvidia-smi >/dev/null || { echo "An NVIDIA GPU with a current driver is required (nvidia-smi not found)."; exit 1; }
PY=.venv-finetune/bin/python
[ -x "$PY" ] || python3 -m venv .venv-finetune

if ! "$PY" -c "import torch, sys; sys.exit(0 if torch.version.cuda else 1)" 2>/dev/null; then
  echo "Installing PyTorch with CUDA (about 2.5 GB, first run only)..."
  "$PY" -m pip install -q --upgrade pip
  "$PY" -m pip install --force-reinstall torch --index-url https://download.pytorch.org/whl/cu126
fi
"$PY" -m pip install -q -r finetune/requirements.txt
"$PY" -c "import torch, sys; sys.exit(0 if torch.cuda.is_available() else 1)" \
  || { echo "PyTorch cannot see your NVIDIA GPU. Check the driver (nvidia-smi) and retry."; exit 1; }

exec "$PY" -m finetune "$@"
