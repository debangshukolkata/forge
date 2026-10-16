@echo off
rem Double-click to start the overnight test run (docs\OVERNIGHT_OFFICE.md explains it). It runs every job once, one after another, and leaves a report in overnight-results\<date-time>\MORNING_REPORT.html.
rem Options go after the name, for example:  Start-Overnight.cmd --dry-run   (shows the plan, runs nothing)   Start-Overnight.cmd --profile extended --max-hours 20
rem To continue a run that was stopped: Start-Overnight.cmd --out overnight-results\<the same folder>
title DebCraft overnight run
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo The private Python environment is missing. Double-click Start-DebCraft.cmd once first, close DebCraft, then start this again.
    pause
    exit /b 1
)
rem The test tools (pytest, xdist, document libraries) are not part of a plain install: add them once, here, so the night does not depend on a manual step.
".venv\Scripts\python.exe" -c "import pytest, xdist, docx, openpyxl" 2>nul
if errorlevel 1 (
    echo Adding the test tools to the private Python environment ^(once, needs the internet^)...
    ".venv\Scripts\python.exe" -m pip install -e ".[dev,docs,webtext]"
    if errorlevel 1 echo WARNING: the test tools could not be installed; the test jobs will be skipped. Check the internet or proxy and start again.
)
set PYTHONIOENCODING=utf-8
".venv\Scripts\python.exe" scripts\overnight\run_overnight.py --env-file "%USERPROFILE%\.forge\.env" %*
echo.
echo The run has ended. Open overnight-results\ and the newest folder, then MORNING_REPORT.html.
pause
