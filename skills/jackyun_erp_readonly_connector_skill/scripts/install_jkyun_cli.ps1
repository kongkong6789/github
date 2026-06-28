$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    throw "python was not found in PATH."
}

@'
from helpers.jkyun_cli import ensure_cli_executable
print(ensure_cli_executable())
'@ | & $python.Source -
