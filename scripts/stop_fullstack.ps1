param(
    [int]$BackendPort = 2024,
    [int]$FrontendPort = 3000
)

$ErrorActionPreference = "Stop"

& (Join-Path $PSScriptRoot "stop_frontend.ps1") -Port $FrontendPort
& (Join-Path $PSScriptRoot "stop_backend.ps1") -Port $BackendPort

Write-Output "A2A frontend and backend stop requested."
