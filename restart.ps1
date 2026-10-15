$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
& "$PSScriptRoot\stop.ps1"
Start-Sleep -Milliseconds 500
& "$PSScriptRoot\start.ps1"
