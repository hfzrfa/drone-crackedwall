$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    throw 'Virtual environment is missing. Run .\run.ps1 first.'
}
if (-not (Test-Path -LiteralPath 'best.pt')) {
    throw 'best.pt is missing.'
}
Remove-Item -LiteralPath 'logs\stop.request' -Force -ErrorAction SilentlyContinue
Write-Host 'Starting server. Press Ctrl+C for a clean shutdown.' -ForegroundColor Green
& .\.venv\Scripts\python.exe server.py
