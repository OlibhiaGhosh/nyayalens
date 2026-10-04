#!/usr/bin/env bash
# NyayLens one-command demo (macOS/Linux). Everything runs on 127.0.0.1; no internet needed.
#   ./run_demo.sh                 # gemma4:e4b
#   NYAYA_MODEL=gemma4:e2b ./run_demo.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export NYAYA_MODEL="${NYAYA_MODEL:-gemma4:e4b}"
export OLLAMA_NUM_PARALLEL=2 OLLAMA_NO_CLOUD=1  # two prompt-cache slots; local only
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || { echo "Missing .venv. Run scripts/setup.sh first."; exit 1; }

if command -v ollama >/dev/null; then
  curl -sf http://127.0.0.1:11434/api/tags >/dev/null || { echo "Starting Ollama..."; (ollama serve >/dev/null 2>&1 &); sleep 3; }
else
  echo "WARNING: Ollama not installed: keyword fallback only."
fi

[ -f "$ROOT/frontend/dist/index.html" ] || (cd "$ROOT/frontend" && npm run build)

cd "$ROOT/backend"
"$PY" -m uvicorn main:app --host 127.0.0.1 --port 8000 &
BACKEND=$!
trap 'kill $BACKEND 2>/dev/null' EXIT
for _ in $(seq 40); do curl -sf http://127.0.0.1:8000/api/selfcheck >/dev/null && break; sleep 0.5; done

echo "Warming up $NYAYA_MODEL ..."
curl -sf -X POST http://127.0.0.1:8000/api/warmup --max-time 600 || echo "warm-up failed"
echo
(command -v xdg-open >/dev/null && xdg-open http://127.0.0.1:8000) || (command -v open >/dev/null && open http://127.0.0.1:8000) || true
echo "NyayLens running at http://127.0.0.1:8000  (Ctrl+C to stop)"
wait $BACKEND
