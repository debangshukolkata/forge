<#
.SYNOPSIS
  Builds an offline wheelhouse for installing Forge on a Windows laptop without internet or admin rights
  (spec §3 packaging, A-6: cp313 win_amd64).

.DESCRIPTION
  Run on a machine WITH internet access. It
    1. builds the Forge wheel from this repository,
    2. downloads every dependency as a binary wheel for CPython 3.13 / win_amd64 (no source builds),
    3. optionally stores Playwright's Chromium for the browser tool,
    4. writes SHA256SUMS.txt, and
    5. proves the set is complete by installing it into a fresh venv with --no-index and running
       `forge --version` and `forge doctor --offline`.
  Copy the output folder (plus scripts\install_forge.ps1 and docs\INSTALL.md) to the laptop.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\build_wheelhouse.ps1
  powershell -ExecutionPolicy Bypass -File scripts\build_wheelhouse.ps1 -Extras "mcp" -IncludeBrowser
#>
[CmdletBinding()]
param(
    [string]$OutDir = "wheels",
    [string]$PythonVersion = "3.13",
    [string]$Extras = "mcp,browser",
    [switch]$IncludeBrowser,
    [switch]$SkipVerify
)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$abi = "cp" + $PythonVersion.Replace(".", "")

function Invoke-Checked([string]$what, [scriptblock]$block) {
    Write-Host "==> $what"
    & $block
    if ($LASTEXITCODE -ne 0) { throw "$what failed (exit code $LASTEXITCODE)" }
}

# The build machine may have several Pythons; the py launcher picks the requested one.
$python = (& py "-$PythonVersion" -c "import sys; print(sys.executable)").Trim()
if ($LASTEXITCODE -ne 0 -or -not $python) { throw "Python $PythonVersion not found (py -$PythonVersion)." }

$out = if ([IO.Path]::IsPathRooted($OutDir)) { $OutDir } else { Join-Path $repo $OutDir }
New-Item -ItemType Directory -Force $out | Out-Null
Get-ChildItem $out -Filter "forge-*.whl" -ErrorAction SilentlyContinue | Remove-Item -Force

Invoke-Checked "Building the Forge wheel" { & $python -m pip wheel $repo --no-deps --wheel-dir $out --quiet }
# pip wheel leaves build/ in the repository; it would otherwise be linted and scanned.
Remove-Item -Recurse -Force (Join-Path $repo "build") -ErrorAction SilentlyContinue
$forgeWheel = Get-ChildItem $out -Filter "forge-*.whl" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$target = if ($Extras) { "$($forgeWheel.FullName)[$Extras]" } else { $forgeWheel.FullName }

Invoke-Checked "Downloading dependencies for $abi win_amd64" {
    & $python -m pip download $target pip setuptools wheel `
        --dest $out --only-binary=:all: --platform win_amd64 `
        --python-version $PythonVersion --implementation cp --abi $abi --abi abi3 --abi none --quiet
}

if ($IncludeBrowser) {
    # Playwright's browsers are not wheels: store Chromium next to the wheels; install_forge.ps1 copies it.
    $browsers = Join-Path $out "ms-playwright"
    $env:PLAYWRIGHT_BROWSERS_PATH = $browsers
    Invoke-Checked "Downloading Playwright Chromium" { & $python -m playwright install chromium }
    Remove-Item Env:PLAYWRIGHT_BROWSERS_PATH
}

Write-Host "==> Writing SHA256SUMS.txt"
Get-ChildItem $out -File -Filter "*.whl" | Sort-Object Name | ForEach-Object {
    "{0}  {1}" -f (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLower(), $_.Name
} | Set-Content -Encoding utf8 (Join-Path $out "SHA256SUMS.txt")

if (-not $SkipVerify) {
    $probe = Join-Path ([IO.Path]::GetTempPath()) ("forge-wheelhouse-check-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
    try {
        Invoke-Checked "Creating a clean venv to verify the wheelhouse" { & $python -m venv $probe }
        $venvPython = Join-Path $probe "Scripts\python.exe"
        $spec = if ($Extras) { "forge[$Extras]" } else { "forge" }
        Invoke-Checked "Installing offline (--no-index)" {
            & $venvPython -m pip install --no-index --find-links $out $spec --quiet
        }
        Invoke-Checked "forge --version" { & (Join-Path $probe "Scripts\forge.exe") --version }
        $env:FORGE_HOME = Join-Path $probe "forge_home"
        & (Join-Path $probe "Scripts\forge.exe") doctor --offline
        Remove-Item Env:FORGE_HOME
        # doctor exits non-zero when keys/DBs are missing, which is expected on a build machine.
    } finally {
        Remove-Item -Recurse -Force $probe -ErrorAction SilentlyContinue
    }
}

$count = (Get-ChildItem $out -Filter "*.whl").Count
Write-Host ""
Write-Host "Wheelhouse ready: $out ($count wheels). Copy it with scripts\install_forge.ps1 and docs\INSTALL.md."
