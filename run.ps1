$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

Write-Host '=== Drone Crack Detection: first-run setup ===' -ForegroundColor Cyan
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    Write-Host '[1/4] Creating Python virtual environment...'
    & python -m venv .venv
} else {
    Write-Host '[1/4] Virtual environment already exists.'
}

Write-Host '[2/4] Installing/updating dependencies...'
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt

if (-not (Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
    Write-Host '[3/4] Created .env from .env.example.'
} else {
    Write-Host '[3/4] Using existing .env.'
}

Write-Host '[4/4] Validating best.pt...'
& .\.venv\Scripts\python.exe .\scripts\test_model.py --validate-only
Write-Host 'Starting Flask server. Press Ctrl+C for a clean shutdown.' -ForegroundColor Green
& .\.venv\Scripts\python.exe server.py
