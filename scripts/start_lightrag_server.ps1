Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$EnvPath = Join-Path $ProjectRoot ".env"
$WorkingDir = Join-Path $ProjectRoot "data\lightrag_official"
$InputDir = Join-Path $ProjectRoot "data\lightrag_inputs"
$PythonScripts = Join-Path $ProjectRoot ".venv\Scripts"
$ServerExe = Join-Path $PythonScripts "lightrag-server.exe"
$LogPath = Join-Path $ProjectRoot "lightrag-server.log"
$ErrPath = Join-Path $ProjectRoot "lightrag-server.err.log"

function Import-DotEnv {
  param([string]$Path)
  if (-not (Test-Path $Path)) { return }
  Get-Content -LiteralPath $Path | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) { return }
    $idx = $line.IndexOf("=")
    $name = $line.Substring(0, $idx).Trim()
    $value = $line.Substring($idx + 1).Trim().Trim('"').Trim("'")
    if ($name) { [Environment]::SetEnvironmentVariable($name, $value, "Process") }
  }
}

Import-DotEnv -Path $EnvPath
New-Item -ItemType Directory -Force -Path $WorkingDir | Out-Null
New-Item -ItemType Directory -Force -Path $InputDir | Out-Null

if (-not (Test-Path $ServerExe)) {
  throw "lightrag-server.exe not found. Run $(Join-Path $PSScriptRoot 'install_lightrag.ps1') first."
}

$env:LIGHTRAG_HOST = if ($env:LIGHTRAG_HOST) { $env:LIGHTRAG_HOST } else { "127.0.0.1" }
$env:LIGHTRAG_PORT = if ($env:LIGHTRAG_PORT) { $env:LIGHTRAG_PORT } else { "9621" }
$env:WORKING_DIR = if ($env:WORKING_DIR) { $env:WORKING_DIR } else { $WorkingDir }
$env:INPUT_DIR = if ($env:INPUT_DIR) { $env:INPUT_DIR } else { $InputDir }
$env:LLM_BINDING = if ($env:LLM_BINDING) { $env:LLM_BINDING } else { "openai" }
$env:LLM_MODEL = if ($env:LLM_MODEL) { $env:LLM_MODEL } elseif ($env:OPENAI_MODEL) { $env:OPENAI_MODEL } else { "gpt-4.1-mini" }
$env:LLM_BINDING_HOST = if ($env:LLM_BINDING_HOST) { $env:LLM_BINDING_HOST } elseif ($env:OPENAI_BASE_URL) { $env:OPENAI_BASE_URL } else { "https://api.openai.com/v1" }
$env:LLM_BINDING_API_KEY = if ($env:LLM_BINDING_API_KEY) { $env:LLM_BINDING_API_KEY } elseif ($env:OPENAI_API_KEY) { $env:OPENAI_API_KEY } else { "" }
$env:EMBEDDING_BINDING = if ($env:EMBEDDING_BINDING) { $env:EMBEDDING_BINDING } else { "openai" }
$env:EMBEDDING_BINDING_HOST = if ($env:EMBEDDING_BINDING_HOST) { $env:EMBEDDING_BINDING_HOST } elseif ($env:OPENAI_BASE_URL) { $env:OPENAI_BASE_URL } else { "https://api.openai.com/v1" }
$env:EMBEDDING_BINDING_API_KEY = if ($env:EMBEDDING_BINDING_API_KEY) { $env:EMBEDDING_BINDING_API_KEY } elseif ($env:OPENAI_API_KEY) { $env:OPENAI_API_KEY } else { "" }
$env:EMBEDDING_MODEL = if ($env:EMBEDDING_MODEL) { $env:EMBEDDING_MODEL } else { "text-embedding-3-small" }
$env:EMBEDDING_DIM = if ($env:EMBEDDING_DIM) { $env:EMBEDDING_DIM } else { "2048" }
$env:EMBEDDING_MAX_TOKEN_SIZE = if ($env:EMBEDDING_MAX_TOKEN_SIZE) { $env:EMBEDDING_MAX_TOKEN_SIZE } else { "8192" }
$env:EMBEDDING_SEND_DIM = if ($env:EMBEDDING_SEND_DIM) { $env:EMBEDDING_SEND_DIM } else { "false" }
$env:EMBEDDING_USE_BASE64 = if ($env:EMBEDDING_USE_BASE64) { $env:EMBEDDING_USE_BASE64 } else { "false" }
$env:A2A_LIGHTRAG_MODE = if ($env:A2A_LIGHTRAG_MODE) { $env:A2A_LIGHTRAG_MODE } else { "official" }
$env:LIGHTRAG_API_URL = if ($env:LIGHTRAG_API_URL) { $env:LIGHTRAG_API_URL } else { "http://127.0.0.1:9621" }

$running = Get-Process -Name "lightrag-server" -ErrorAction SilentlyContinue
if ($running) {
  Write-Output "LightRAG server process already running."
  return
}

Start-Process -FilePath $ServerExe -WorkingDirectory $ProjectRoot -RedirectStandardOutput $LogPath -RedirectStandardError $ErrPath -WindowStyle Hidden
Start-Sleep -Seconds 3
Write-Output "LightRAG server starting at $env:LIGHTRAG_API_URL"
Write-Output "Logs: $LogPath"
Write-Output "Errors: $ErrPath"
