#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="${ROOT_DIR}/logs"
BUILD_LOG="${LOG_DIR}/apex_installer_build_linux.log"

mkdir -p "${LOG_DIR}"

on_error() {
	local exit_code="$?"
	echo "[ERRO] Build falhou com código ${exit_code}. Verifique ${BUILD_LOG}" | tee -a "${BUILD_LOG}"
	echo "===== END $(date '+%Y-%m-%d %H:%M:%S') (failed: ${exit_code}) =====" >> "${BUILD_LOG}"
	exit "${exit_code}"
}

trap on_error ERR

echo "===== START $(date '+%Y-%m-%d %H:%M:%S') =====" >> "${BUILD_LOG}"
echo "[INFO] Build do instalador Linux/Mac (target linux)"
echo "[INFO] Log: ${BUILD_LOG}"

echo "[1/2] Instalando dependências npm..."
npm install >> "${BUILD_LOG}" 2>&1

echo "[2/2] Gerando instalador Linux com electron-builder..."
npx electron-builder --linux >> "${BUILD_LOG}" 2>&1

echo "[OK] Build finalizado com sucesso. Artefatos em dist/"
echo "===== END $(date '+%Y-%m-%d %H:%M:%S') (success) =====" >> "${BUILD_LOG}"
