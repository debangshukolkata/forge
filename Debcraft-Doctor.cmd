@echo off
rem Double-click to check this computer for DebCraft (D-412): Python and packages, certificates, your .env, the models (Azure and Gemini), the databases,
rem the web search and Node. It prints one line per check (OK, WARN or FAIL) and saves the same text to doctor-report.txt in this folder, so you can send it.
rem No key or token is printed. Needs DebCraft to be installed here already: double-click Start-DebCraft.cmd once first if there is no .venv folder.
title DebCraft doctor
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo DebCraft is not installed in this folder yet. Double-click Start-DebCraft.cmd once, close DebCraft, then run this again.
    pause
    exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "& '.venv\Scripts\python.exe' -m forge doctor 2>&1 | Tee-Object -FilePath 'doctor-report.txt'"
echo.
echo Saved to %~dp0doctor-report.txt  (send this file, or a photo of the screen, if something says FAIL)
pause
