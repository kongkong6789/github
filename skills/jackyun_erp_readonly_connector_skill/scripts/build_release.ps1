$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$versionFile = Join-Path $projectRoot "VERSION"
$distDir = Join-Path $projectRoot "dist"

if (-not (Test-Path $versionFile)) {
    throw "VERSION file not found."
}

$version = (Get-Content $versionFile -Raw).Trim()
if (-not $version) {
    throw "VERSION is empty."
}

New-Item -ItemType Directory -Force -Path $distDir | Out-Null

$packageName = "jackyun-erp-skill-$version.zip"
$packagePath = Join-Path $distDir $packageName

if (Test-Path $packagePath) {
    Remove-Item -LiteralPath $packagePath -Force
}

$exclude = @(
    ".git",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "data",
    ".DS_Store"
)

$stagingDir = Join-Path $distDir "_release_staging"
if (Test-Path $stagingDir) {
    Remove-Item -LiteralPath $stagingDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $stagingDir | Out-Null

$items = Get-ChildItem -LiteralPath $projectRoot -Force | Where-Object {
    $exclude -notcontains $_.Name -and $_.Name -notlike "tmp_*"
}
foreach ($item in $items) {
    Copy-Item -LiteralPath $item.FullName -Destination $stagingDir -Recurse -Force
}

$cacheDir = Join-Path $projectRoot "data/cache"
if (Test-Path $cacheDir) {
    $stagingCacheDir = Join-Path $stagingDir "data/cache"
    New-Item -ItemType Directory -Force -Path $stagingCacheDir | Out-Null
    Copy-Item -Path (Join-Path $cacheDir "*.json") -Destination $stagingCacheDir -Force -ErrorAction SilentlyContinue
}

Compress-Archive -Path (Join-Path $stagingDir "*") -DestinationPath $packagePath -Force
Remove-Item -LiteralPath $stagingDir -Recurse -Force

Write-Output "Built release package:"
Write-Output $packagePath
