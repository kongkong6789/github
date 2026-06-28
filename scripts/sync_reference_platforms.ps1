$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Target = Join-Path $Root "_references"
New-Item -ItemType Directory -Force -Path $Target | Out-Null

function Clone-Or-Update {
    param(
        [string]$Name,
        [string]$Url
    )
    $Dir = Join-Path $Target $Name
    if (Test-Path (Join-Path $Dir ".git")) {
        Write-Host "Updating $Name..."
        git -C $Dir fetch --depth 1 origin
        git -C $Dir checkout -q main 2>$null
        if ($LASTEXITCODE -ne 0) {
            git -C $Dir checkout -q master 2>$null
        }
        git -C $Dir pull --ff-only --depth 1
    }
    else {
        Write-Host "Cloning $Name..."
        git clone --depth 1 $Url $Dir
    }
}

Clone-Or-Update "duckdb" "https://github.com/duckdb/duckdb.git"
Clone-Or-Update "LightRAG" "https://github.com/HKUDS/LightRAG.git"
Clone-Or-Update "MiroFish" "https://github.com/666ghj/MiroFish.git"
Clone-Or-Update "ruoyi-ai" "https://github.com/ageerle/ruoyi-ai.git"
Clone-Or-Update "MaxKB" "https://github.com/1Panel-dev/MaxKB.git"

$WikiPath = Join-Path $Target "karpathy-llm-wiki.md"
Invoke-WebRequest -Uri "https://gist.githubusercontent.com/karpathy/442a6bf555914893e9891c11519de94f/raw" -OutFile $WikiPath

Write-Host "Reference snapshots synced under $Target"
