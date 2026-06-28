Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Script:ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Script:ProjectRoot = Split-Path -Parent $Script:ScriptDir
$Script:RuntimeDir = if ($env:A2A_RUNTIME_DIR) {
    $env:A2A_RUNTIME_DIR
} else {
    Join-Path $Script:ProjectRoot ".runtime"
}

New-Item -ItemType Directory -Force -Path $Script:RuntimeDir | Out-Null

function Import-A2ADotEnv {
    param([string]$Path = (Join-Path $Script:ProjectRoot ".env"))

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    Get-Content -LiteralPath $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            return
        }

        $index = $line.IndexOf("=")
        $name = $line.Substring(0, $index).Trim()
        $value = $line.Substring($index + 1).Trim().Trim('"').Trim("'")
        if ($name) {
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

function Find-A2AVenvExecutable {
    param([Parameter(Mandatory = $true)][string]$Name)

    $candidates = @(
        Join-Path $Script:ProjectRoot ".venv\Scripts\$Name.exe",
        Join-Path $Script:ProjectRoot ".venv\Scripts\$Name",
        Join-Path $Script:ProjectRoot ".venv\bin\$Name"
    )

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }

    return $null
}

function Find-A2APython {
    if ($env:A2A_PYTHON_BIN -and (Test-Path -LiteralPath $env:A2A_PYTHON_BIN)) {
        return $env:A2A_PYTHON_BIN
    }

    $venvPython = Find-A2AVenvExecutable -Name "python"
    if ($venvPython) {
        return $venvPython
    }

    $command = Get-Command python -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $python3 = Get-Command python3 -ErrorAction SilentlyContinue
    if ($python3) {
        return $python3.Source
    }

    throw "Python runtime not found."
}

function Test-A2AHttp {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [int]$TimeoutSeconds = 5
    )

    try {
        Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSeconds | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Wait-A2AHttp {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [int]$TimeoutSeconds = 45
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-A2AHttp -Url $Url) {
            return $true
        }
        Start-Sleep -Seconds 2
    }
    return $false
}

function Stop-A2APortProcess {
    param([Parameter(Mandatory = $true)][int]$Port)

    $connections = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
    foreach ($connection in $connections) {
        $process = Get-Process -Id $connection.OwningProcess -ErrorAction SilentlyContinue
        if ($process) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        }
    }
}

