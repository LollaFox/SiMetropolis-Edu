@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0" || exit /b 1
if not exist ".venv\Scripts\python.exe" (
    echo This copy of SiMetropolis Edu still needs to be set up.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -B -m classroom launch
if errorlevel 1 (
    pause
    exit /b 1
)
