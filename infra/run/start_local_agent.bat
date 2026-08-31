@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

set "LOG_DIR=%CD%\logs"
set "RUN_LOG=%LOG_DIR%\local_agent_main.out.log"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo ============================================
echo [APEX] Local Agent - Startup
echo ============================================

where node >nul 2>nul
if errorlevel 1 (
  echo [ERRO] Node.js nao encontrado. Instale Node.js 18+ e tente novamente. >> "%RUN_LOG%"
  echo [ERRO] Node.js nao encontrado. Instale Node.js 18+ e tente novamente.
  exit /b 1
)

where npm >nul 2>nul
if errorlevel 1 (
  echo [ERRO] npm nao encontrado. Instale npm e tente novamente. >> "%RUN_LOG%"
  echo [ERRO] npm nao encontrado. Instale npm e tente novamente.
  exit /b 1
)

echo [OK] Node:
node -v
echo [OK] npm:
call npm -v

echo [INFO] Instalando dependencias (express, cors, ws)...
call npm install --no-save express cors ws
if errorlevel 1 (
  echo [ERRO] Falha ao instalar dependencias Node. >> "%RUN_LOG%"
  echo [ERRO] Falha ao instalar dependencias Node.
  exit /b 1
)

echo [INFO] Iniciando local_agent_main.js
echo [INFO] Log: %RUN_LOG%
echo.

echo ===== START %DATE% %TIME% =====>> "%RUN_LOG%"
node local_agent_main.js >> "%RUN_LOG%" 2>&1
set "EXIT_CODE=%ERRORLEVEL%"
echo ===== END %DATE% %TIME% (exit !EXIT_CODE!) =====>> "%RUN_LOG%"

if not "%EXIT_CODE%"=="0" (
  echo [ERRO] local_agent_main.js finalizou com codigo %EXIT_CODE%.
  exit /b %EXIT_CODE%
)

echo [OK] local_agent_main.js finalizado com sucesso.
exit /b 0
