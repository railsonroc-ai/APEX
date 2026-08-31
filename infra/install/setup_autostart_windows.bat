@echo off
chcp 65001 > nul
echo ============================================
echo 🔧 Configurar Inicialização Automática
echo ============================================
echo.
echo Este script criará uma tarefa agendada para
echo iniciar o APEX Dashboard automaticamente
echo quando o Windows iniciar.
echo.
echo Pressione qualquer tecla para continuar...
pause > nul

REM Obtém o caminho completo do diretório atual
set "SCRIPT_DIR=%~dp0"
set "START_SCRIPT=%SCRIPT_DIR%start.bat"

echo.
echo 📝 Criando tarefa agendada...

REM Remove tarefa existente se houver
schtasks /delete /tn "APEX_Dashboard" /f > nul 2>&1

REM Cria nova tarefa
schtasks /create /tn "APEX_Dashboard" /tr "\"%START_SCRIPT%\"" /sc onlogon /rl highest /f

if errorlevel 1 (
    echo.
    echo ❌ Erro ao criar tarefa agendada
    echo 💡 Execute este script como Administrador
    echo.
    pause
    exit /b 1
)

echo.
echo ✅ Tarefa agendada criada com sucesso!
echo.
echo ============================================
echo 🎯 Configuração Completa!
echo ============================================
echo.
echo O APEX Dashboard agora iniciará automaticamente
echo quando você fizer login no Windows.
echo.
echo Para desabilitar:
echo 1. Abra o Agendador de Tarefas do Windows
echo 2. Encontre "APEX_Dashboard"
echo 3. Desabilite ou exclua a tarefa
echo.
echo ============================================
echo.
pause
