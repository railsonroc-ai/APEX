#!/bin/bash

echo "============================================"
echo "🔧 Configurar Inicialização Automática"
echo "============================================"
echo ""
echo "Este script criará um serviço systemd para"
echo "iniciar o APEX Dashboard automaticamente"
echo "quando o sistema iniciar."
echo ""

# Obtém o diretório atual e usuário
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CURRENT_USER=$(whoami)

# Verifica se está rodando como root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Este script precisa ser executado como root"
    echo "💡 Execute: sudo ./setup_autostart_linux.sh"
    exit 1
fi

echo "📝 Criando serviço systemd..."

# Cria arquivo de serviço
cat > /etc/systemd/system/apex-dashboard.service << EOF
[Unit]
Description=APEX Dashboard Service
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$SCRIPT_DIR
ExecStart=$SCRIPT_DIR/venv/bin/python3 $SCRIPT_DIR/apex_automation.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Recarrega systemd
systemctl daemon-reload

# Habilita o serviço
systemctl enable apex-dashboard.service

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Erro ao criar serviço"
    exit 1
fi

echo ""
echo "✅ Serviço criado com sucesso!"
echo ""
echo "============================================"
echo "🎯 Configuração Completa!"
echo "============================================"
echo ""
echo "Comandos úteis:"
echo "  sudo systemctl start apex-dashboard    # Iniciar serviço"
echo "  sudo systemctl stop apex-dashboard     # Parar serviço"
echo "  sudo systemctl status apex-dashboard   # Ver status"
echo "  sudo systemctl restart apex-dashboard  # Reiniciar"
echo "  sudo systemctl disable apex-dashboard  # Desabilitar auto-start"
echo ""
echo "Logs:"
echo "  sudo journalctl -u apex-dashboard -f  # Ver logs em tempo real"
echo ""
echo "============================================"
echo ""

# Pergunta se quer iniciar agora
read -p "Deseja iniciar o serviço agora? (s/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Ss]$ ]]; then
    systemctl start apex-dashboard.service
    echo ""
    echo "✅ Serviço iniciado!"
    echo "🌐 Acesse: http://localhost:5000"
fi

echo ""
