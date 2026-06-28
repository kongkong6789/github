Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Requirements = Join-Path $ProjectRoot "requirements-lightrag.txt"

if (-not (Test-Path $Python)) {
  throw "Python venv not found: $Python"
}

if (-not (Test-Path $Requirements)) {
  throw "Requirements file not found: $Requirements"
}

& $Python -m pip install -r $Requirements
