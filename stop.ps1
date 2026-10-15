$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$project = [regex]::Escape((Resolve-Path $PSScriptRoot).Path)
$servers = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -in @('python.exe', 'pythonw.exe') -and $_.CommandLine -match "$project.*server\.py"
}
if (-not $servers) {
    Write-Host 'Server tidak sedang berjalan.'
    return
}

New-Item -ItemType Directory -Path 'logs' -Force | Out-Null
New-Item -ItemType File -Path 'logs\stop.request' -Force | Out-Null
Write-Host 'Clean shutdown requested; waiting for session CSV...'
$deadline = (Get-Date).AddSeconds(12)
do {
    Start-Sleep -Milliseconds 300
    $remaining = @($servers | Where-Object { Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue })
} while ($remaining.Count -gt 0 -and (Get-Date) -lt $deadline)

if ($remaining.Count -gt 0) {
    Write-Warning 'Clean shutdown timed out. Stopping only this project server process.'
    $remaining | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}
Remove-Item -LiteralPath 'logs\stop.request' -Force -ErrorAction SilentlyContinue
Write-Host 'Server stopped.'
