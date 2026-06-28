param(
    [switch]$Json,
    [int]$RecentAuditLines = 200
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$Python = Join-Path $Root ".venv/bin/python"

if (-not (Test-Path -LiteralPath $Python)) {
    $Python = Join-Path $Root ".venv/Scripts/python.exe"
}
if (-not (Test-Path -LiteralPath $Python)) {
    $Python = "python"
}

$ArgsList = @("scripts/doctor.py", "--recent-audit-lines", "$RecentAuditLines")
if ($Json) {
    $ArgsList += "--json"
}

Push-Location $Root
try {
    & $Python @ArgsList
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
