@echo off
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\AzerothCore-Server.ps1" -Action Start
if errorlevel 1 (
  echo.
  pause
) else (
  timeout /t 8 >nul
)
