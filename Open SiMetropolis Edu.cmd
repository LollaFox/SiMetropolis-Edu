@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0" || exit /b 1
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\launch-classroom-windows.ps1"
if errorlevel 1 (
    pause
    exit /b 1
)
