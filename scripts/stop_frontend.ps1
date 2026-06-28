param(
    [int]$Port = 3000
)

$ErrorActionPreference = "Stop"

$connections = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
$pids = @($connections | Select-Object -ExpandProperty OwningProcess -Unique)

foreach ($processId in $pids) {
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if ($process -and $process.ProcessName -in @("node", "powershell")) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
}

Write-Output "Stopped frontend processes on port $Port when present."
