#!/bin/bash
# Script para iniciar o APEX localmente

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR" || exit 1

echo "Iniciando APEX localmente..."

# Ativa o ambiente virtual, se existir
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Garante que a pasta de logs existe
mkdir -p logs

# Inicia o backend salvando logs e o PID
nohup gunicorn --chdir backend app:app --bind 0.0.0.0:${PORT:-5001} > logs/backend.log 2>&1 &
echo $! > logs/backend.pid

echo "APEX rodando em background (PID $(cat logs/backend.pid)). Logs em logs/backend.log."
