@echo off
rem Double-click to find out which model suits which role (D-655): the same challenge for the Gemini and Azure models.
rem Takes about 3 to 5 hours and can run overnight. Every step is saved: after a stop, double-click again and it goes on.
rem Needs Start-DebCraft.cmd to have run once in this folder. At the end the report opens in the browser.
title DebCraft role challenge
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Double-click Start-DebCraft.cmd in this folder first; it sets up Python. Then close DebCraft and come back.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" scripts\dev\role_challenge.py %*
echo.
echo Finished or stopped. Double-click this file again to go on with what is missing, or to open the report.
pause
