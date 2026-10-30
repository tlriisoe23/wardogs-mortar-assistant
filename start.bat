@echo off
title WARDOGS Ballistic Audio Assistant
cd /d "%~dp0"
if exist "%~dp0src-tauri\target\release\wardogs-mortar-assistant-desktop.exe" (
    start "" "%~dp0src-tauri\target\release\wardogs-mortar-assistant-desktop.exe"
    exit /b 0
)
echo Starting WARDOGS Mortar Audio Assistant...
python server.py
pause
