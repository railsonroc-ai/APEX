#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Ativa ambiente virtual se existir
if [ -f venv/bin/activate ]; then
    source venv/bin/activate
fi

echo "============================================"
echo "  APEX — Professor IA"
echo "============================================"
echo ""
echo "Iniciando servidor em http://127.0.0.1:5001"
echo ""

python3 app.py
