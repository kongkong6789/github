Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot

function Clear-DirectoryContents {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Path,
    [string[]]$ExcludeNames = @()
  )

  if (-not (Test-Path -LiteralPath $Path)) {
    return
  }

  Get-ChildItem -LiteralPath $Path -Force | Where-Object {
    $ExcludeNames -notcontains $_.Name
  } | ForEach-Object {
    Remove-Item -LiteralPath $_.FullName -Recurse -Force
  }
}

$targets = @(
  @{ Path = (Join-Path $ProjectRoot ".langgraph_api"); Exclude = @() },
  @{ Path = (Join-Path $ProjectRoot "data\tasks"); Exclude = @() },
  @{ Path = (Join-Path $ProjectRoot "data\lightrag"); Exclude = @() },
  @{ Path = (Join-Path $ProjectRoot "data\lightrag_inputs"); Exclude = @() },
  @{ Path = (Join-Path $ProjectRoot "data\lightrag_official"); Exclude = @() },
  @{ Path = (Join-Path $ProjectRoot "wiki"); Exclude = @(".obsidian") }
)

& (Join-Path $PSScriptRoot "stop_backend.ps1")
& (Join-Path $PSScriptRoot "stop_lightrag_server.ps1")

foreach ($target in $targets) {
  if (-not (Test-Path -LiteralPath $target.Path)) {
    New-Item -ItemType Directory -Force -Path $target.Path | Out-Null
    continue
  }

  Clear-DirectoryContents -Path $target.Path -ExcludeNames $target.Exclude
}

$wikiIndex = Join-Path $ProjectRoot "wiki\index.md"
if (Test-Path -LiteralPath $wikiIndex) {
  Remove-Item -LiteralPath $wikiIndex -Force
}

Write-Output "Cleared Obsidian wiki content, LightRAG data, and conversation history."
