param(
    [int]$Port = 3000,
    [string]$HostName = "127.0.0.1",
    [int]$StartupTimeoutSeconds = 45
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$FrontendRoot = Join-Path $Root "agent-chat-ui"
$NextBin = Join-Path $FrontendRoot "node_modules\next\dist\bin\next"
$WindowTitle = "A2A Frontend"

. (Join-Path $PSScriptRoot "common.ps1")
Import-A2ADotEnv
if (-not $PSBoundParameters.ContainsKey("Port") -and $env:A2A_FRONTEND_PORT) {
    $Port = [int]$env:A2A_FRONTEND_PORT
}

$NodeExe = if ($env:A2A_NODE_BIN) {
    $env:A2A_NODE_BIN
} elseif (Get-Command node.exe -ErrorAction SilentlyContinue) {
    (Get-Command node.exe).Source
} elseif (Get-Command node -ErrorAction SilentlyContinue) {
    (Get-Command node).Source
} else {
    $null
}

if (-not (Test-Path -LiteralPath $FrontendRoot)) {
    throw "Frontend directory not found: $FrontendRoot"
}

if (-not $NodeExe -or -not (Test-Path -LiteralPath $NodeExe)) {
    throw "Node runtime not found. Set A2A_NODE_BIN or ensure node/node.exe is available on PATH."
}

if (-not (Test-Path -LiteralPath $NextBin)) {
    throw "Next.js binary not found: $NextBin"
}

& (Join-Path $PSScriptRoot "stop_frontend.ps1") -Port $Port

$command = @"
Set-Location -LiteralPath '$FrontendRoot'
`$Host.UI.RawUI.WindowTitle = '$WindowTitle'
& '$NodeExe' '$NextBin' dev --hostname $HostName --port $Port
"@

Start-Process `
    -FilePath "powershell.exe" `
    -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $command) `
    -WorkingDirectory $FrontendRoot

$deadline = (Get-Date).AddSeconds($StartupTimeoutSeconds)
$started = $false
while ((Get-Date) -lt $deadline) {
    try {
        $response = Invoke-WebRequest "http://$HostName`:$Port" -UseBasicParsing -TimeoutSec 5
        if ($response.StatusCode -eq 200) {
            $started = $true
            break
        }
    } catch {
        # continue polling until frontend responds
    }
    Start-Sleep -Seconds 2
}

if (-not $started) {
    throw "Frontend did not start listening on port $Port within $StartupTimeoutSeconds seconds."
}

Write-Output "Frontend is listening on http://$HostName`:$Port"
