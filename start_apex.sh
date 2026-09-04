#!/usr/bin/env bash
set -e

mkdir -p logs data/memories data/backups

PORT="${PORT:-5000}"
WORKERS="${WEB_CONCURRENCY:-2}"
THREADS="${WEB_THREADS:-4}"

echo "Inicializando schema do APEX..."
python3 - <<'PYDB'
from backend.database import init_database

init_database()
print("Banco APEX: OK")
PYDB

echo "Iniciando APEX na porta $PORT com $WORKERS workers e $THREADS threads..."

exec gunicorn backend.app:app \
    --workers "$WORKERS" \
    --threads "$THREADS" \
    --timeout 120 \
    --keep-alive 5 \
    --bind "0.0.0.0:$PORT" \
    --access-logfile logs/access.log \
    --error-logfile logs/error.log
