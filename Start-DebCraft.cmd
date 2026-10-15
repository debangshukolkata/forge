@echo off
rem Double-click to start DebCraft from this folder (D-230). First run: creates a private Python environment
rem inside this folder (.venv) and installs DebCraft into it, which needs internet for pip once. Later runs reuse
rem it and just start DebCraft. After downloading a newer DebCraft, double-click this file in the new folder.
rem The install step lists each package as pip fetches it (a few minutes the first time).
rem Before DebCraft opens it runs the doctor (one line per check, saved in doctor-report.txt); set DEBCRAFT_SKIP_DOCTOR=1 to skip it.
rem Needs Python 3.13 installed for your user (no admin rights). No data in %USERPROFILE%\.forge is touched.
title DebCraft
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\run_forge.ps1" -Extras "mcp,browser,audit,slides,gemini"
if errorlevel 1 (
    echo.
    echo DebCraft did not start. The message above says why.
    echo If it says DebCraft is still running, close its window first. If it says Python 3.13 was not found, install it from python.org for your user only. Then double-click this file again.
    pause
)
