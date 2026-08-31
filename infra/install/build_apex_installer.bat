@echo off
setlocal enabledelayedexpansion
chcp 65001 > nul
title APEX - Build Installer (.exe)

cd /d "%~dp0"

set "ROOT=%CD%"
set "LOG_DIR=%ROOT%\logs"
set "BUILD_LOG=%LOG_DIR%\apex_installer_build.log"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo ===== START %DATE% %TIME% =====>> "%BUILD_LOG%"
echo [INFO] Build do instalador .exe do APEX
echo [INFO] Log: %BUILD_LOG%

echo [1/2] Instalando dependências npm...
call npm install >> "%BUILD_LOG%" 2>&1
if errorlevel 1 (
  echo [ERRO] npm install falhou. Verifique %BUILD_LOG%.
  echo ===== END %DATE% %TIME% (npm install failed) =====>> "%BUILD_LOG%"
  exit /b 1
)

echo [2/2] Gerando instalador Windows (.exe) com electron-builder...
call npx electron-builder --win >> "%BUILD_LOG%" 2>&1
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
  echo [ERRO] electron-builder falhou com código %EXIT_CODE%. Verifique %BUILD_LOG%.
  echo ===== END %DATE% %TIME% (build failed: %EXIT_CODE%) =====>> "%BUILD_LOG%"
  exit /b %EXIT_CODE%
)

echo [OK] Instalador gerado com sucesso em dist\
echo ===== END %DATE% %TIME% (success) =====>> "%BUILD_LOG%"
exit /b 0
