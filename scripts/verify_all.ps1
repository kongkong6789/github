Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

& (Join-Path $PSScriptRoot "verify_python.ps1")
& (Join-Path $PSScriptRoot "verify_frontend.ps1")
