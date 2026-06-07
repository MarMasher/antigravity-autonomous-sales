@echo off
title Antigravity Daemon
:: Disable QuickEdit mode so clicking the console doesn't pause it
reg add "HKCU\Console" /v QuickEdit /t REG_DWORD /d 0 /f >nul

:: Change to the directory where this script lives (works from any location)
cd /d "%~dp0"
echo.
echo  ==========================================
echo   ANTIGRAVITY — Autonomous Pipeline Daemon
echo  ==========================================
echo.
echo  Starting daemon... (runs every 24h automatically)
echo  Logs: logs\daemon.log
echo  Close this window to stop.
echo.
python daemon.py
