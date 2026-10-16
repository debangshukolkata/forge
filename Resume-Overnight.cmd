@echo off
rem Double-click to continue the newest overnight run where it stopped (after a shutdown, a restart, a pause or Ctrl+C). Finished jobs are kept; the job that was running starts again from its beginning.
rem Extra options go after the name, for example:  Resume-Overnight.cmd --retry   (also run again what failed or was skipped)
title DebCraft overnight run (resume)
cd /d "%~dp0"
call Start-Overnight.cmd --out latest %*
