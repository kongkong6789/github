param(
    [switch]$UnitOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "common.ps1")
Import-A2ADotEnv

$FrontendDir = Join-Path $Script:ProjectRoot "agent-chat-ui"
if (-not (Test-Path -LiteralPath $FrontendDir)) {
    throw "Frontend directory not found: $FrontendDir"
}

Push-Location $FrontendDir
try {
    $WithEnv = Join-Path $FrontendDir "scripts/with-env-node.sh"
    $Esbuild = Join-Path $FrontendDir "node_modules/.bin/esbuild"
    $Tsc = Join-Path $FrontendDir "node_modules/.bin/tsc"

    if (-not (Test-Path -LiteralPath $WithEnv) -or -not (Test-Path -LiteralPath $Esbuild) -or -not (Test-Path -LiteralPath $Tsc)) {
        throw "Frontend dependencies are missing. Run npm install or pnpm install in agent-chat-ui first."
    }

    $testSources = Get-ChildItem -Path (Join-Path $FrontendDir "src") -Recurse -File |
        Where-Object { $_.Name -like "*.test.ts" -or $_.Name -like "*.test.tsx" } |
        Sort-Object FullName |
        ForEach-Object { $_.FullName }

    if ($testSources.Count -gt 0) {
        $tmpDir = Join-Path ([System.IO.Path]::GetTempPath()) ("a2a-ui-tests." + [System.Guid]::NewGuid().ToString("N"))
        New-Item -ItemType Directory -Force -Path $tmpDir | Out-Null
        try {
            & bash $WithEnv $Esbuild @testSources --bundle --platform=node --format=esm "--outdir=$tmpDir" "--external:node:*"
            $testBundles = Get-ChildItem -Path $tmpDir -Recurse -File -Filter "*.test.js" |
                Sort-Object FullName |
                ForEach-Object { $_.FullName }
            & bash $WithEnv node --test @testBundles
        } finally {
            Remove-Item -LiteralPath $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
        }
    } else {
        Write-Output "No frontend test files found under agent-chat-ui/src."
    }

    if (-not $UnitOnly) {
        & bash $WithEnv $Tsc --noEmit --pretty false
        npm run build
    }
} finally {
    Pop-Location
}
