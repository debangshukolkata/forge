# Creates the fixture app's own venv (tests/fixtures/sample_repo/backend/venv), the way a real
# host app keeps its venv inside the app folder (spec §2). Forge's tests reuse this interpreter.
param(
    [string]$PythonVersion = "3.13"
)
$ErrorActionPreference = "Stop"

$backend = Join-Path $PSScriptRoot "..\..\tests\fixtures\sample_repo\backend" | Resolve-Path
$venv = Join-Path $backend "venv"

if (-not (Test-Path (Join-Path $venv "Scripts\python.exe"))) {
    & py "-$PythonVersion" -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw "Could not create venv with Python $PythonVersion" }
}

$python = Join-Path $venv "Scripts\python.exe"
& $python -m pip install --quiet --upgrade pip
& $python -m pip install --quiet -r (Join-Path $backend "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

Write-Host "Fixture venv ready: $python"
