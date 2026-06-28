Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

param(
    [Parameter(Mandatory = $true)]
    [string]$Sql,
    [int]$Limit = 50
)

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$EscapedSql = $Sql.Replace("`"", "`"`"")

& $Python -c "from src.a2a_ecommerce_demo.fact_layer_tools import query_fact_layer; print(query_fact_layer(r'''$EscapedSql''', limit=$Limit))"
