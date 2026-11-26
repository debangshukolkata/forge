@echo off
rem Double-click for everything the office laptop owes DebCraft (D-660): it asks a few things once, then runs the checks,
rem holds the conversations in the WisdomNext project by itself, runs the live tests and ends with pages to photograph.
rem About 2 to 3 hours with a requirement, 1 to 2 without. You may leave it running. Close DebCraft first.
title DebCraft laptop report
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Double-click Start-DebCraft.cmd in this folder first; it sets up Python. Then close DebCraft and come back.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m forge.cli laptop all
echo.
echo Finished. Photograph every page above (they are also saved in .forge\laptop_report in your user folder).
pause
