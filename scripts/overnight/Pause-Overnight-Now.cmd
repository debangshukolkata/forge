@echo off
rem Double-click to stop the overnight run NOW, before you shut the laptop. The job that is running is stopped and starts again from its beginning when you continue with Resume-Overnight.cmd.
cd /d "%~dp0"
for /f "delims=" %%F in ('dir /b /ad /o-d "overnight-results" 2^>nul') do (
    if exist "overnight-results\%%F\state.json" (
        echo stop> "overnight-results\%%F\STOP_NOW"
        echo Stop requested for overnight-results\%%F. Wait until the run window says it has paused (about 30 seconds), then you can shut the laptop down.
        goto :done
    )
)
echo No overnight run was found.
:done
pause
