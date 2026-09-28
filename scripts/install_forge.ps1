<#
.SYNOPSIS
  Installs Forge from an offline wheelhouse, per user, without admin rights (docs\INSTALL.md).

.DESCRIPTION
  Creates a private venv under %LOCALAPPDATA%\Forge\venv (outside every repository, so Forge's own install
  is never inside a folder it works on), installs Forge from the wheelhouse with --no-index, prepares
  %USERPROFILE%\.forge with a .env template, copies Playwright's Chromium when the wheelhouse has it, and
  adds a `forge.cmd` shim to %LOCALAPPDATA%\Forge\bin (you add that folder to your user PATH).
  Re-running it upgrades Forge in place; your .env and config.yaml are never overwritten.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File install_forge.ps1 -Wheelhouse .\wheels
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Wheelhouse,
    [string]$PythonVersion = "3.13",
    [string]$Extras = "mcp,browser",
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA "Forge"),
    [string]$ForgeHome = $(if ($env:FORGE_HOME) { $env:FORGE_HOME } else { Join-Path $env:USERPROFILE ".forge" })
)
$ErrorActionPreference = "Stop"
$wheels = (Resolve-Path $Wheelhouse).Path

function Invoke-Checked([string]$what, [scriptblock]$block) {
    Write-Host "==> $what"
    & $block
    if ($LASTEXITCODE -ne 0) { throw "$what failed (exit code $LASTEXITCODE)" }
}

$sums = Join-Path $wheels "SHA256SUMS.txt"
if (Test-Path $sums) {
    Write-Host "==> Checking wheel hashes"
    foreach ($line in Get-Content $sums) {
        $expected, $name = $line -split "\s+", 2
        $actual = (Get-FileHash (Join-Path $wheels $name) -Algorithm SHA256).Hash.ToLower()
        if ($actual -ne $expected) { throw "Hash mismatch for $name - the wheelhouse copy is damaged." }
    }
}

$python = $null
try { $python = (& py "-$PythonVersion" -c "import sys; print(sys.executable)").Trim() } catch { }
if (-not $python) {
    $candidate = Join-Path $env:LOCALAPPDATA ("Programs\Python\Python" + $PythonVersion.Replace(".", "") + "\python.exe")
    if (Test-Path $candidate) { $python = $candidate }
}
if (-not $python) { throw "Python $PythonVersion not found. Install it per user from python.org (no admin needed), then re-run." }

$venv = Join-Path $InstallRoot "venv"
if (-not (Test-Path (Join-Path $venv "Scripts\python.exe"))) {
    Invoke-Checked "Creating $venv" { & $python -m venv $venv }
}
$venvPython = Join-Path $venv "Scripts\python.exe"
$spec = if ($Extras) { "forge[$Extras]" } else { "forge" }
Invoke-Checked "Installing Forge (offline)" {
    & $venvPython -m pip install --no-index --find-links $wheels --upgrade $spec --quiet --disable-pip-version-check
}

$browsers = Join-Path $wheels "ms-playwright"
if (Test-Path $browsers) {
    $target = Join-Path $env:LOCALAPPDATA "ms-playwright"
    Write-Host "==> Copying Playwright Chromium to $target"
    Copy-Item -Recurse -Force (Join-Path $browsers "*") (New-Item -ItemType Directory -Force $target).FullName
}

New-Item -ItemType Directory -Force $ForgeHome | Out-Null
$envFile = Join-Path $ForgeHome ".env"
if (-not (Test-Path $envFile)) {
    @(
        "# Forge secrets. Fill in, keep private, never commit.",
        "AZURE_OPENAI_ENDPOINT=",
        "AZURE_OPENAI_API_VERSION=",
        "AZURE_OPENAI_DEPLOYMENT=",
        "AZURE_OPENAI_SECONDARY_DEPLOYMENT=",
        "AZURE_OPENAI_API_KEY=",
        "LOCAL_PG_URL=",
        "DEV_PG_URL=",
        "SERPAPI_API_KEY=",
        "TAVILY_API_KEY="
    ) | Set-Content -Encoding utf8 $envFile
    Write-Host "==> Created $envFile (fill in your Azure OpenAI values)"
}

$bin = Join-Path $InstallRoot "bin"
New-Item -ItemType Directory -Force $bin | Out-Null
"@echo off`r`n`"$venv\Scripts\forge.exe`" %*" | Set-Content -Encoding ascii (Join-Path $bin "forge.cmd")

& (Join-Path $venv "Scripts\forge.exe") --version
Write-Host ""
Write-Host "Installed. Next steps:"
Write-Host "  1. Add $bin to your user PATH (Settings > 'Edit environment variables for your account')."
Write-Host "  2. Edit $envFile with your Azure OpenAI endpoint, deployment and key."
Write-Host "  3. Open a new PowerShell and run:  forge doctor"
