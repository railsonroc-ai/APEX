@echo off
setlocal enabledelayedexpansion
chcp 65001 > nul
title APEX — Professor IA

cd /d "%~dp0"

set "ROOT=%CD%"
set "LOG_DIR=%ROOT%\logs"
set "BACKEND_LOG=%LOG_DIR%\backend.log"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo ============================================
echo   APEX — Professor IA
echo ============================================
echo.
echo [INFO] Log: %BACKEND_LOG%
echo [INFO] Iniciando servidor Flask...

REM Ativa ambiente virtual se existir
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

start "APEX" cmd /c "cd /d "%ROOT%" && python app.py >> "%BACKEND_LOG%" 2>&1"

timeout /t 2 > nul

echo [INFO] Abrindo navegador em http://localhost:5001
start "" "http://localhost:5001"

echo.
echo ✅ APEX iniciado. Acesse http://localhost:5001
echo.
exit /b 0

