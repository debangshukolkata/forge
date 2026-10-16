@echo off
rem Double-click to continue the newest overnight run AND run again every job that failed, had problems, timed out, stalled or was skipped (jobs that passed are kept).
title DebCraft overnight run (resume and retry)
cd /d "%~dp0"
call Resume-Overnight.cmd --retry
