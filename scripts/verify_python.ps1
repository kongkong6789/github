Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Ruff = Join-Path $ProjectRoot ".venv\Scripts\ruff.exe"
$Pyright = Join-Path $ProjectRoot ".venv\Scripts\pyright.exe"

Write-Host "[1/4] compileall"
& $Python -c "import compileall, sys; ok = compileall.compile_dir(r'$ProjectRoot\\src', quiet=1) and compileall.compile_dir(r'$ProjectRoot\\tests', quiet=1); print('compileall', ok); sys.exit(0 if ok else 1)"

Write-Host "[2/4] unittest"
& $Python -c "import sys, unittest; suite = unittest.defaultTestLoader.discover(r'$ProjectRoot\\tests'); result = unittest.TextTestRunner(verbosity=1).run(suite); sys.exit(0 if result.wasSuccessful() else 1)"

Write-Host "[3/4] ruff"
if (Test-Path $Ruff) {
    & $Ruff check "$ProjectRoot\src" "$ProjectRoot\tests" "$ProjectRoot\scripts"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    Write-Host "ruff not installed in .venv; skipped"
}

Write-Host "[4/4] pyright"
if (Test-Path $Pyright) {
    & $Pyright
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    Write-Host "pyright not installed in .venv; skipped"
}
