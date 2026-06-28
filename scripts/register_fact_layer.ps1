Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

& $Python -c "from src.a2a_ecommerce_demo.fact_layer_tools import register_all_fact_datasets; print(register_all_fact_datasets())"
