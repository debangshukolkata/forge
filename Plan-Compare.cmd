@echo off
rem DP2 (D-663): Hydrogen and Argon plan one very complex task, Hydrogen merges the two plans as DebCraft does, and
rem the three plans open on one page without their authors. About 10 to 20 minutes. DebCraft may stay open.
title DebCraft plan compare
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Double-click Start-DebCraft.cmd in this folder first; it sets up Python.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" scripts\dev\plan_compare.py %*
echo.
echo Photograph the page that opened, top to bottom. Do not run it with --key until Claude has judged the plans.
pause
