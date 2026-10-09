<#
.SYNOPSIS
  Gets a freshly unzipped Forge folder running: venv, install, open UI. One command (D-145/D-146).

.DESCRIPTION
  For someone who downloaded and unzipped the Forge source (not the per-user shared install that
  install_forge.ps1 does into %LOCALAPPDATA%). Creates a venv INSIDE this folder (.venv), installs Forge into
  it from this same unzipped source, then opens the web UI - which itself now guides through Azure OpenAI keys
  and a live connectivity check (D-146) if none are set up yet. Re-running it is safe: an existing .venv is
  reused, not recreated, so this also works as "just start Forge" once already set up.

  Deliberately does not touch %USERPROFILE%\.forge\.env itself - the web UI's own setup screen (D-146) already
  covers entering and verifying keys, so this script's only job is getting to that screen, not duplicating it.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\run_forge.ps1
#>
[CmdletBinding()]
param(
    [string]$PythonVersion = "3.13",
    [string]$Extras = "",
    [string]$Wheelhouse = ""
)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Invoke-Checked([string]$what, [scriptblock]$block) {
    Write-Host "==> $what"
    & $block
    if ($LASTEXITCODE -ne 0) { throw "$what failed (exit code $LASTEXITCODE)" }
}

# The venv lives inside this same unzipped folder, not %LOCALAPPDATA% - a plain unzipped folder has no
# earlier install to reuse or collide with, so there is nothing to shim onto PATH and nothing that can end up
# shadowed by a different, older Forge install the way a global `forge` on PATH silently can (seen live: a
# stray %LOCALAPPDATA%\Forge\venv from install_forge.ps1 shadowed a freshly replaced repo folder's own copy).
$venv = Join-Path $root ".venv"
$venvPython = Join-Path $venv "Scripts\python.exe"
$venvForge = Join-Path $venv "Scripts\forge.exe"

$firstRun = -not (Test-Path $venvPython)
if ($firstRun) {
    $python = $null
    try { $python = (& py "-$PythonVersion" -c "import sys; print(sys.executable)").Trim() } catch { }
    if (-not $python) {
        $candidate = Join-Path $env:LOCALAPPDATA ("Programs\Python\Python" + $PythonVersion.Replace(".", "") + "\python.exe")
        if (Test-Path $candidate) { $python = $candidate }
    }
    if (-not $python) {
        throw "Python $PythonVersion not found. Install it per user from python.org (no admin needed), then re-run this script."
    }
    Invoke-Checked "Creating $venv" { & $python -m venv $venv }
} else {
    Write-Host "==> Reusing existing $venv"
}

# A previous `forge ui` from this same folder locks its own .exe on Windows: reinstalling over a running
# instance fails with a raw, confusing WinError 32. Caught here with a clear message instead (seen live).
if (Test-Path $venvForge) {
    $locked = $false
    try {
        $stream = [System.IO.File]::Open($venvForge, "Open", "ReadWrite", "None")
        $stream.Close()
    } catch {
        $locked = $true
    }
    if ($locked) {
        throw "Forge is still running from this folder (its own forge.exe is locked). Close that window " +
            "or stop the process first, then re-run this script."
    }
}

# The first install lists every package as it is fetched (it takes minutes); later starts stay quiet.
$pipVerbosity = if ($firstRun) { @("--progress-bar", "off") } else { @("--quiet") }
$spec = if ($Extras) { ".[$Extras]" } else { "." }
if ($Wheelhouse) {
    # Matches install_forge.ps1's offline path: a wheelhouse folder bundled alongside the unzipped source
    # means no network is needed at install time, for the real office-laptop-may-be-offline case (CLAUDE.md).
    $wheels = (Resolve-Path $Wheelhouse).Path
    Invoke-Checked "Installing Forge from $root (offline, wheelhouse $wheels)" {
        & $venvPython -m pip install --no-index --find-links $wheels -e $spec --disable-pip-version-check @pipVerbosity
    }
} else {
    Invoke-Checked "Installing Forge from $root" {
        & $venvPython -m pip install -e $spec --disable-pip-version-check @pipVerbosity
    }
}

Write-Host "==> Starting Forge UI"
& $venvForge ui
