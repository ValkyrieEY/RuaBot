@echo off
REM Xiaoyi_QQ Framework Startup Script for Windows
REM Author: ValkyrieEY

echo Starting Xiaoyi_QQ Framework...

REM Get the directory where this script is located
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

REM Check Python
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Python not found. Please install Python 3.11+
    pause
    exit /b 1
)

echo Python found

REM Create necessary directories
if not exist "data" mkdir data
if not exist "logs" mkdir logs
if not exist "plugins" mkdir plugins

REM Run the application
echo   [SCLI] Starting application...
echo   [SCLI] Web UI: http://localhost:8000
echo   [SCLI] API Docs: http://localhost:8000/docs
echo ============================================================

python -m src.main

