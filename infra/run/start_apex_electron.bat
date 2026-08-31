@echo off
setlocal enabledelayedexpansion
chcp 65001 > nul
title APEX Electron - Startup

cd /d "%~dp0"

set "ROOT=%CD%"
set "LOG_DIR=%ROOT%\logs"
set "RUN_LOG=%LOG_DIR%\apex_electron_start.log"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo ===== START %DATE% %TIME% =====>> "%RUN_LOG%"
echo [INFO] Iniciando APEX via Electron...
echo [INFO] Log: %RUN_LOG%

echo [INFO] Instalando dependências npm...
call npm install >> "%RUN_LOG%" 2>&1
if errorlevel 1 (
  echo [ERRO] Falha ao instalar dependências. Verifique %RUN_LOG%.
  echo ===== END %DATE% %TIME% (npm install failed) =====>> "%RUN_LOG%"
  exit /b 1
)

echo [INFO] Executando npx electron .
call npx electron . >> "%RUN_LOG%" 2>&1
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
  echo [ERRO] Electron finalizou com código %EXIT_CODE%. Verifique %RUN_LOG%.
  echo ===== END %DATE% %TIME% (exit %EXIT_CODE%) =====>> "%RUN_LOG%"
  exit /b %EXIT_CODE%
)

echo [OK] APEX Electron finalizado com sucesso.
echo ===== END %DATE% %TIME% (exit 0) =====>> "%RUN_LOG%"
exit /b 0
