@echo off
rem Double-click for what the office laptop owes DebCraft (D-660, D-661). No questions, nothing on WisdomNext: the roles,
rem Gemini 4 Argon step by step, two conversations in a test project of the sample repository, the live tests, then pages
rem to photograph. About 1 to 1.5 hours; you may leave it running. Close DebCraft first.
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
