# ⚡ Guia Rápido - APEX Dashboard Automation

## 🚀 Início Rápido (3 passos)

### Windows
```bash
1. install.bat       # Instala tudo automaticamente
2. start.bat         # Inicia o sistema
3. Acesse: http://localhost:5000
```

### Linux/Mac
```bash
1. chmod +x *.sh && ./install.sh   # Instala
2. ./start.sh                       # Inicia
3. Acesse: http://localhost:5000
```

---

## 📋 Comandos Principais

| Comando | Descrição |
|---------|-----------|
| `python apex_automation.py` | Inicia com automação completa |
| `python apex_automation.py status` | Mostra status do sistema |
| `python apex_automation.py backup` | Cria backup manual |
| `python apex_automation.py restart` | Reinicia o dashboard |
| `python apex_automation.py stop` | Para o dashboard |

---

## 🎯 O que o sistema faz automaticamente?

✅ **Instala dependências** se estiverem faltando
✅ **Inicia o dashboard** Flask automaticamente  
✅ **Monitora** o dashboard a cada 30 segundos
✅ **Reinicia** automaticamente se travar
✅ **Cria backups** a cada 6 horas
✅ **Limpa backups** antigos (mantém 10)
✅ **Organiza logs** por data
✅ **Exibe status** em tempo real

---

## 📂 Onde está cada coisa?

```
📁 backups/          ← Seus backups automáticos
📁 logs/             ← Logs do sistema
📁 templates/        ← Templates HTML
📄 dashboard.py      ← Seu dashboard Flask
📄 output.json       ← Seus dados
🤖 apex_automation.py ← O cérebro da automação
```

---

## 🔧 Configurar Inicialização Automática

### Windows (Admin)
```bash
setup_autostart_windows.bat
```

### Linux (sudo)
```bash
sudo ./setup_autostart_linux.sh
```

Após configurar, o dashboard inicia sozinho quando você ligar o PC!

---

## 🆘 Problemas Comuns

### "Porta 5000 já em uso"
**Windows:**
```bash
netstat -ano | findstr :5000
taskkill /PID [número] /F
```

**Linux/Mac:**
```bash
lsof -ti:5000 | xargs kill -9
```

### "Python não encontrado"
Instale Python 3.8+: https://www.python.org/downloads/

### Dashboard não abre
1. Veja os logs: `logs/apex_automation_[data].log`
2. Rode: `python apex_automation.py status`
3. Reinstale: `pip install -r requirements.txt`

---

## 🎨 Personalizar

Edite `config.json`:

```json
{
    "dashboard": {
        "port": 5000        ← Mude a porta aqui
    },
    "backup": {
        "interval_hours": 6  ← Mude frequência do backup
    }
}
```

---

## 📊 Ver Status

Execute:
```bash
python apex_automation.py status
```

Você verá:
```
📊 APEX DASHBOARD - STATUS DO SISTEMA
Status: 🟢 ONLINE
Uptime: 2:34:15
PID: 12345
URL: http://localhost:5000
Backups: 5/10
```

---

## 🎉 Dica Pro

Crie um atalho na área de trabalho:

**Windows:** Clique direito em `start.bat` → Enviar para → Área de trabalho

**Linux:** Crie um `.desktop` file ou adicione ao menu

---

## 💡 Recursos Extras

- 📊 **Dashboard Web**: http://localhost:5000
- 📈 **API Status**: http://localhost:5000/api/status
- 📉 **API Stats**: http://localhost:5000/api/stats
- 📥 **Export Excel**: http://localhost:5000/api/export/excel
- 📄 **Export CSV**: http://localhost:5000/api/export/csv

---

## 🎯 Atalhos Úteis

| Atalho | Ação |
|--------|------|
| `Ctrl + C` | Para o sistema |
| `start.bat` / `start.sh` | Inicia rapidamente |
| `install.bat` / `install.sh` | Reinstala/Atualiza |

---

**🚀 É isso! Seu notebook está totalmente automatizado!**

Qualquer dúvida, consulte o `README.md` completo.
