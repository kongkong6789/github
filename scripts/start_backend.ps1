param(
    [int]$Port = 2024,
    [string]$HostName = "127.0.0.1",
    [int]$StartupTimeoutSeconds = 45
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$LangGraph = Join-Path $Root ".venv\Scripts\langgraph.exe"
$OutLog = Join-Path $Root "langgraph-server.log"
$ErrLog = Join-Path $Root "langgraph-server.err.log"

. (Join-Path $PSScriptRoot "common.ps1")
Import-A2ADotEnv
if (-not $PSBoundParameters.ContainsKey("Port") -and $env:A2A_BACKEND_PORT) {
    $Port = [int]$env:A2A_BACKEND_PORT
}

if (-not (Test-Path -LiteralPath $LangGraph)) {
    throw "LangGraph executable not found: $LangGraph"
}

& (Join-Path $PSScriptRoot "stop_backend.ps1") -Port $Port

Remove-Item -LiteralPath $OutLog, $ErrLog -Force -ErrorAction SilentlyContinue

$backendEnv = @{
    PYTHONUTF8 = "1"
}
foreach ($entry in $backendEnv.GetEnumerator()) {
    Set-Item -Path "Env:$($entry.Key)" -Value $entry.Value
}

Start-Process `
    -FilePath $LangGraph `
    -ArgumentList @("dev", "--host", $HostName, "--port", "$Port", "--no-browser", "--no-reload", "--n-jobs-per-worker", "1") `
    -WorkingDirectory $Root `
    -WindowStyle Hidden `
    -RedirectStandardOutput $OutLog `
    -RedirectStandardError $ErrLog

$deadline = (Get-Date).AddSeconds($StartupTimeoutSeconds)
$healthy = $false
while ((Get-Date) -lt $deadline) {
    try {
        & (Join-Path $PSScriptRoot "health_backend.ps1") -Port $Port -HostName $HostName | Out-Null
        $healthy = $true
        break
    } catch {
        Start-Sleep -Seconds 2
    }
}

if (-not $healthy) {
    throw "Backend did not become healthy within $StartupTimeoutSeconds seconds. Check $OutLog and $ErrLog."
}

Write-Output "Backend is healthy on http://$HostName`:$Port"
