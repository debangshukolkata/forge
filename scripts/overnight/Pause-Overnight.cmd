@echo off
rem Double-click to pause the overnight run AFTER the job that is running now has finished. The window of the run closes itself. Continue later with Resume-Overnight.cmd.
cd /d "%~dp0"
for /f "delims=" %%F in ('dir /b /ad /o-d "overnight-results" 2^>nul') do (
    if exist "overnight-results\%%F\state.json" (
        echo pause> "overnight-results\%%F\STOP"
        echo Pause requested for overnight-results\%%F. The job that is running will finish first; you can see when the run window closes.
        goto :done
    )
)
echo No overnight run was found.
:done
pause
