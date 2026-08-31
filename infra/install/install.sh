#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
APEX_DIR="${ROOT_DIR}/apex"
LOG_DIR="${APEX_DIR}/logs"
AGENT_DIR="${APEX_DIR}/agent"
BACKEND_DIR="${APEX_DIR}/backend"
INSTALL_LOG="${LOG_DIR}/install.log"
START_SCRIPT="${ROOT_DIR}/start_apex.sh"
SERVICE_FILE="${ROOT_DIR}/apex.service"

mkdir -p "${LOG_DIR}"
exec > >(tee -a "${INSTALL_LOG}") 2>&1

echo "============================================"
echo "🚀 APEX - Instalador Completo (Linux/Mac)"
echo "============================================"
echo "📁 Root: ${ROOT_DIR}"
echo "📝 Log:  ${INSTALL_LOG}"
echo

echo "[1/7] Verificando dependências de sistema..."
if ! command -v node >/dev/null 2>&1; then
    echo "❌ Node.js não encontrado."
    echo "💡 Linux: instale via gerenciador de pacotes da distro"
    echo "💡 macOS: brew install node"
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ Python3 não encontrado."
    echo "💡 Linux: sudo apt install python3"
    echo "💡 macOS: brew install python"
    exit 1
fi

if ! command -v pip3 >/dev/null 2>&1; then
    echo "❌ pip3 não encontrado."
    echo "💡 Linux: sudo apt install python3-pip"
    echo "💡 macOS: python3 -m ensurepip --upgrade"
    exit 1
fi

echo "✅ Node:   $(node -v)"
echo "✅ Python: $(python3 --version)"
echo "✅ pip3:   $(pip3 --version | awk '{print $1, $2}')"
echo

echo "[2/7] Criando estrutura de pastas..."
mkdir -p "${APEX_DIR}" "${LOG_DIR}" "${AGENT_DIR}" "${BACKEND_DIR}"
echo "✅ Pastas criadas:"
echo "   - ${APEX_DIR}"
echo "   - ${LOG_DIR}"
echo "   - ${AGENT_DIR}"
echo "   - ${BACKEND_DIR}"
echo

echo "[3/7] Instalando dependências do backend (pip3 install -r requirements.txt)..."
cd "${ROOT_DIR}"
pip3 install -r requirements.txt
echo "✅ Dependências Python instaladas"
echo

echo "[4/7] Instalando dependências do agente local (npm install)..."
npm install
echo "✅ Dependências Node instaladas"
echo

echo "[5/7] Gerando script start_apex.sh..."
cat > "${START_SCRIPT}" <<'EOF'
#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
APEX_DIR="${ROOT_DIR}/apex"
LOG_DIR="${APEX_DIR}/logs"
BACKEND_LOG="${LOG_DIR}/backend.log"
AGENT_LOG="${LOG_DIR}/agent.log"
BACKEND_PID_FILE="${APEX_DIR}/backend/backend.pid"
AGENT_PID_FILE="${APEX_DIR}/agent/agent.pid"

mkdir -p "${LOG_DIR}" "${APEX_DIR}/backend" "${APEX_DIR}/agent"

start_background() {
    echo "[APEX] Iniciando backend em background..."
    nohup python3 "${ROOT_DIR}/apex_server.py" >> "${BACKEND_LOG}" 2>&1 &
    echo $! > "${BACKEND_PID_FILE}"

    sleep 1

    echo "[APEX] Iniciando agente local em background..."
    nohup node "${ROOT_DIR}/local_agent_main.js" >> "${AGENT_LOG}" 2>&1 &
    echo $! > "${AGENT_PID_FILE}"

    echo "✅ APEX iniciado em background"
    echo "🌐 Backend: http://localhost:5000"
    echo "📝 Logs:"
    echo "   - ${BACKEND_LOG}"
    echo "   - ${AGENT_LOG}"
}

start_foreground() {
    echo "[APEX] Iniciando backend e agente local (foreground)..."
    python3 "${ROOT_DIR}/apex_server.py" >> "${BACKEND_LOG}" 2>&1 &
    BACKEND_PID=$!
    echo "${BACKEND_PID}" > "${BACKEND_PID_FILE}"

    node "${ROOT_DIR}/local_agent_main.js" >> "${AGENT_LOG}" 2>&1 &
    AGENT_PID=$!
    echo "${AGENT_PID}" > "${AGENT_PID_FILE}"

    trap 'kill ${BACKEND_PID} ${AGENT_PID} >/dev/null 2>&1 || true' INT TERM EXIT
    wait -n ${BACKEND_PID} ${AGENT_PID}
}

if [[ "${1:-}" == "--foreground" ]]; then
    start_foreground
else
    start_background
fi
EOF

chmod +x "${START_SCRIPT}"
echo "✅ Script criado: ${START_SCRIPT}"
echo

echo "[6/7] Gerando serviço systemd opcional (apex.service)..."
cat > "${SERVICE_FILE}" <<EOF
[Unit]
Description=APEX Stack (Backend + Local Agent)
After=network.target

[Service]
Type=simple
WorkingDirectory=${ROOT_DIR}
ExecStart=${START_SCRIPT} --foreground
Restart=always
RestartSec=5
User=${USER}
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

echo "✅ Arquivo de serviço criado: ${SERVICE_FILE}"

if command -v systemctl >/dev/null 2>&1; then
    if [[ "${APEX_INSTALL_SYSTEMD:-0}" == "1" ]]; then
        echo "[6.1/7] Instalando serviço no systemd..."
        sudo cp "${SERVICE_FILE}" /etc/systemd/system/apex.service
        sudo systemctl daemon-reload
        echo "✅ Serviço instalado em /etc/systemd/system/apex.service"
        echo "💡 Para habilitar no boot: sudo systemctl enable apex.service"
        echo "💡 Para iniciar agora:     sudo systemctl start apex.service"
    else
        echo "ℹ️ Instalação no systemd não aplicada (opcional)."
        echo "   Para instalar automaticamente rode: APEX_INSTALL_SYSTEMD=1 ./install.sh"
    fi
else
    echo "ℹ️ systemd não disponível (normal no macOS). Arquivo apex.service foi apenas gerado."
fi
echo

echo "[7/7] Finalizando..."
echo "✅ APEX instalado com sucesso"
echo "🚀 Para iniciar: ./start_apex.sh"
echo "📝 Log de instalação: ${INSTALL_LOG}"
