param(
    [int]$Port = 2024
)

$ErrorActionPreference = "Stop"

$connections = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
$pids = @($connections | Select-Object -ExpandProperty OwningProcess -Unique)

$langgraphProcesses = Get-Process -Name "langgraph" -ErrorAction SilentlyContinue
foreach ($process in $langgraphProcesses) {
    if ($pids.Count -eq 0 -or $pids -contains $process.Id) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
}

foreach ($processId in $pids) {
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if ($process -and $process.ProcessName -in @("langgraph", "python")) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
}

Write-Output "Stopped LangGraph processes on port $Port when present."
