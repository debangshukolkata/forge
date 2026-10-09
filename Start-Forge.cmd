@echo off
rem Double-click to start Forge from this folder (D-230). First run: creates a private Python environment
rem inside this folder (.venv) and installs Forge into it, which needs internet for pip once. Later runs reuse
rem it and just start Forge. After downloading a newer Forge, double-click this file in the new folder.
rem Needs Python 3.13 installed for your user (no admin rights). No data in %USERPROFILE%\.forge is touched.
title Forge
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\run_forge.ps1" -Extras "mcp,browser"
if errorlevel 1 (
    echo.
    echo Forge did not start. The message above says why.
    echo If it says Forge is still running, close its window first. If it says Python 3.13 was not found, install it from python.org for your user only. Then double-click this file again.
    pause
)
