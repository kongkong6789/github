Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "common.ps1")

Import-A2ADotEnv
$Python = Find-A2APython

Push-Location $Script:ProjectRoot
try {
    & $Python (Join-Path $PSScriptRoot "repair_thread_archives.py") @args
    exit $LASTEXITCODE
} finally {
    Pop-Location
}

