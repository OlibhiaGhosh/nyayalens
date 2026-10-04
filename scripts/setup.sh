#!/usr/bin/env bash
# One-time setup with internet (macOS/Linux). Install Ollama and Tesseract with your package manager first.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
[ -d "$ROOT/.venv" ] || python3 -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/python" -m pip install -q --upgrade pip
"$ROOT/.venv/bin/python" -m pip install -q -r "$ROOT/backend/requirements.txt"
(cd "$ROOT/frontend" && npm ci && npm run build)
"$ROOT/.venv/bin/python" "$ROOT/scripts/download_models.py"
"$ROOT/.venv/bin/python" "$ROOT/samples/make_samples.py"
echo "Setup complete. Start with: ./run_demo.sh"
