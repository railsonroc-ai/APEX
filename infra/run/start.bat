@echo off
chcp 65001 > nul
title APEX — Professor IA

cd /d "%~dp0"

REM Ativa ambiente virtual se existir
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

echo ============================================
echo   APEX — Professor IA
echo ============================================
echo.
echo Iniciando servidor em http://127.0.0.1:5001
echo.

python app.py

pause
