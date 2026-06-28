param(
    [int]$Port = 2024,
    [string]$HostName = "127.0.0.1"
)

$ErrorActionPreference = "Stop"
$Url = "http://${HostName}:${Port}/ok"

try {
    $response = Invoke-RestMethod -Uri $Url -TimeoutSec 10
    $response | ConvertTo-Json -Depth 5
} catch {
    Write-Output "Backend health check failed: $($_.Exception.Message)"
    $Root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
    $ErrLog = Join-Path $Root "langgraph-server.err.log"
    if (Test-Path -LiteralPath $ErrLog) {
        Write-Output "--- langgraph-server.err.log tail ---"
        Get-Content -LiteralPath $ErrLog -Tail 80
    }
    exit 1
}
