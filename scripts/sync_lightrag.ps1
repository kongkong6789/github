Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

& $Python -c "from src.a2a_ecommerce_demo.lightrag_tools import sync_obsidian_to_official_lightrag; print(sync_obsidian_to_official_lightrag())"
