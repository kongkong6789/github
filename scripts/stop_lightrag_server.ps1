Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$processes = Get-Process -Name "lightrag-server" -ErrorAction SilentlyContinue
if (-not $processes) {
  Write-Output "No LightRAG server process found."
  return
}

foreach ($process in $processes) {
  Stop-Process -Id $process.Id -Force
  Write-Output "Stopped LightRAG server process $($process.Id)."
}
