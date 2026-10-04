# NyayLens one-command demo (Windows). Everything runs on 127.0.0.1; no internet needed.
#   powershell -ExecutionPolicy Bypass -File run_demo.ps1            # production build on :8000
#   powershell -ExecutionPolicy Bypass -File run_demo.ps1 -Model gemma4:e2b   # slower laptops
param([string]$Model = "gemma4:e4b")

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
$env:NYAYA_MODEL = $Model
# Two cache slots keep both long system prompts (money terms, clause analysis) cached.
$env:OLLAMA_NUM_PARALLEL = "2"
$env:OLLAMA_NO_CLOUD = "1"
$py = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $py)) { throw "Missing .venv. Run scripts\setup.ps1 first." }

# 1. Ollama (keeps Gemma loaded between requests)
if (Get-Command ollama -ErrorAction SilentlyContinue) {
    try { Invoke-RestMethod http://127.0.0.1:11434/api/tags -TimeoutSec 2 | Out-Null }
    catch {
        Write-Host "Starting Ollama..."
        Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden
        Start-Sleep -Seconds 3
    }
    Write-Host "Tip: if the Ollama tray app was already running, quit it and re-run this script so OLLAMA_NUM_PARALLEL=2 applies."
} else {
    Write-Warning "Ollama is not installed: the app will run with the keyword fallback only."
}

# 2. Frontend build (served by the backend from the same origin)
if (-not (Test-Path (Join-Path $root "frontend\dist\index.html"))) {
    Push-Location (Join-Path $root "frontend"); npm run build; Pop-Location
}

# 3. Backend on 127.0.0.1 only
$backend = Start-Process $py -ArgumentList "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000" `
    -WorkingDirectory (Join-Path $root "backend") -PassThru -NoNewWindow
for ($i = 0; $i -lt 40; $i++) {
    try { Invoke-RestMethod http://127.0.0.1:8000/api/selfcheck -TimeoutSec 2 | Out-Null; break } catch { Start-Sleep -Milliseconds 500 }
}

# 4. Warm the model so the first real request is fast
Write-Host "Warming up $Model and caching prompts (1-2 min on CPU)..."
try { Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/warmup -TimeoutSec 600 | Format-List } catch { Write-Warning "Warm-up failed: $_" }

Start-Process "http://127.0.0.1:8000"
Write-Host "NyayLens running at http://127.0.0.1:8000  (Ctrl+C to stop)"
Wait-Process -Id $backend.Id
