@echo off
rem LN1 (D-667): the learnings DebCraft collected, numbered L1, L2, ... in their own browser tab, names of the company hidden.
rem Takes about a minute; DebCraft may stay open. Read the page before you photograph it.
title DebCraft learnings
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Double-click Start-DebCraft.cmd in this folder first; it sets up Python.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m forge.cli laptop learnings
pause
