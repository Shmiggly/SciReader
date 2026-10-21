# First-time setup for SciReader on Windows (no admin rights needed).
# Requires: uv (https://docs.astral.sh/uv/), Node.js LTS, git. Optional: Ollama for the AI features.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

foreach ($tool in @("uv", "node", "npm")) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { throw "$tool is not installed or not on PATH" }
}

if (-not (Test-Path (Join-Path $root ".env"))) {
    Copy-Item (Join-Path $root ".env.example") (Join-Path $root ".env")
    Write-Host "Created .env from .env.example (edit it to move the data or model folders)."
}

Write-Host "Installing the Python backend (PyTorch with CUDA, Docling, Kokoro)..."
uv sync --directory (Join-Path $root "backend")
if ($LASTEXITCODE -ne 0) { throw "uv sync failed" }

Write-Host "Installing the UI and the math-speech helper..."
npm --prefix (Join-Path $root "frontend") ci
npm --prefix (Join-Path $root "tools\math-speech") ci

Write-Host "Downloading models (Kokoro voice, Docling layout/table/formula models)..."
$env:HF_HUB_OFFLINE = "0"
uv run --directory (Join-Path $root "backend") python -m scireader.setup_models
if ($LASTEXITCODE -ne 0) { throw "model download failed" }

Write-Host "Building the UI..."
npm --prefix (Join-Path $root "frontend") run build

if (Get-Command ollama -ErrorAction SilentlyContinue) {
    Write-Host "Ollama found. Pull the AI models from the app's model manager, or run: ollama pull qwen3.5:9b"
} else {
    Write-Host "Ollama not found: the reader works without it; AI features (narration checks, figures, explain) need it."
}
Write-Host "Done. Start SciReader with ./scripts/dev.ps1"
