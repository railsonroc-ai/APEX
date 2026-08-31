#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

LOG_DIR="${SCRIPT_DIR}/logs"
RUN_LOG="${LOG_DIR}/local_agent_main.out.log"

mkdir -p "$LOG_DIR"

echo "============================================"
echo "🤖 APEX Local Agent - Startup"
echo "============================================"

# Ativa ambiente Node (nvm) se disponível
if [ -s "$HOME/.nvm/nvm.sh" ]; then
    # shellcheck disable=SC1090
    source "$HOME/.nvm/nvm.sh"
fi

if ! command -v node >/dev/null 2>&1; then
    echo "❌ Node.js não encontrado. Instale Node.js 18+ e tente novamente." | tee -a "$RUN_LOG"
    exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
    echo "❌ npm não encontrado. Instale npm e tente novamente." | tee -a "$RUN_LOG"
    exit 1
fi

echo "✅ Node: $(node -v)"
echo "✅ npm:  $(npm -v)"

echo "📦 Instalando dependências Node (express, cors, ws)..."
npm install --no-save express cors ws

echo "🚀 Iniciando local_agent_main.js"
echo "📄 Log de execução: $RUN_LOG"
echo ""

node local_agent_main.js 2>&1 | tee -a "$RUN_LOG"
