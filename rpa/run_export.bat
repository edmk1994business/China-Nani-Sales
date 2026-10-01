@echo off
REM Daily iikoChain -> Dropbox export. Called by Windows Task Scheduler.
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" iiko_export.py
) else (
  python iiko_export.py
)
exit /b %ERRORLEVEL%
