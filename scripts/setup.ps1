# One-time setup with internet (Windows). Afterwards the demo runs fully offline.
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1 [-InstallSystemDeps]
param([switch]$InstallSystemDeps)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent

if ($InstallSystemDeps) {
    winget install --id Ollama.Ollama -e --accept-source-agreements --accept-package-agreements
    winget install --id UB-Mannheim.TesseractOCR -e --accept-source-agreements --accept-package-agreements
}

if (-not (Test-Path "$root\.venv")) { python -m venv "$root\.venv" }
& "$root\.venv\Scripts\python.exe" -m pip install -q --upgrade pip
& "$root\.venv\Scripts\python.exe" -m pip install -q -r "$root\backend\requirements.txt"

Push-Location "$root\frontend"; npm ci; npm run build; Pop-Location

& "$root\.venv\Scripts\python.exe" "$root\scripts\download_models.py"
& "$root\.venv\Scripts\python.exe" "$root\samples\make_samples.py"
Write-Host "Setup complete. Start with: powershell -ExecutionPolicy Bypass -File run_demo.ps1"
