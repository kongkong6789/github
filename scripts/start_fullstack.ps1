param(
    [int]$BackendPort = 2024,
    [int]$FrontendPort = 3000,
    [string]$HostName = "127.0.0.1"
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
. (Join-Path $PSScriptRoot "common.ps1")
Import-A2ADotEnv

if (-not $PSBoundParameters.ContainsKey("BackendPort") -and $env:A2A_BACKEND_PORT) {
    $BackendPort = [int]$env:A2A_BACKEND_PORT
}
if (-not $PSBoundParameters.ContainsKey("FrontendPort") -and $env:A2A_FRONTEND_PORT) {
    $FrontendPort = [int]$env:A2A_FRONTEND_PORT
}

& (Join-Path $PSScriptRoot "start_backend.ps1") -Port $BackendPort -HostName $HostName
& (Join-Path $PSScriptRoot "start_frontend.ps1") -Port $FrontendPort -HostName $HostName

Start-Sleep -Seconds 5
Start-Process "http://$HostName`:$FrontendPort"

Write-Output "A2A stack startup requested. Frontend URL: http://$HostName`:$FrontendPort"
