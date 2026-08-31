@echo off
setlocal enabledelayedexpansion
chcp 65001 > nul

:: ============================================
:: 🚀 APEX Dashboard - Instalador Automático
:: ============================================

echo.
echo ============================================
echo 🚀 Iniciando instalação do APEX Dashboard
echo ============================================
echo.

:: --------------------------------------------
:: Verificar Python
:: --------------------------------------------
echo 🔍 Verificando instalação do Python...

python --version > nul 2>&1
if errorlevel 1 (
    echo ❌ Python não foi encontrado no sistema!
    echo 💡 Baixe e instale em: https://www.python.org/downloads/
    pause
    goto error
)

for /f "tokens=2 delims= " %%v in ('python --version') do set PYVER=%%v
echo ✅ Python encontrado! Versão: %PYVER%
echo.

:: --------------------------------------------
:: Criar ambiente virtual
:: --------------------------------------------
echo 📦 Criando ambiente virtual (venv)...

if exist venv (
    echo ⚠️ Ambiente virtual já existe. Reutilizando...
) else (
    python -m venv venv
    if errorlevel 1 (
        echo ❌ Falha ao criar ambiente virtual!
        pause
        goto error
    )
    echo ✅ Ambiente virtual criado!
)

echo.
echo 🔄 Ativando ambiente virtual...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ❌ Não foi possível ativar o ambiente virtual!
    pause
    goto error
)
echo ✅ Ambiente virtual ativado!
echo.

:: --------------------------------------------
:: Instalar dependências
:: --------------------------------------------
echo 📥 Instalando dependências do projeto...
python -m pip install --upgrade pip > nul

pip install -r requirements.txt
if errorlevel 1 (
    echo ❌ Erro ao instalar dependências!
    pause
    goto error
)

echo.
echo 🔍 Verificando instalação do Flask...
pip show flask > nul
if errorlevel 1 (
    echo ❌ Flask não foi instalado corretamente!
    pause
    goto error
)

echo ✅ Dependências instaladas com sucesso!
echo.

:: --------------------------------------------
:: Criar pastas essenciais
:: --------------------------------------------
echo 🗂️ Verificando pastas necessárias...

for %%p in (logs backups downloads) do (
    if not exist %%p (
        mkdir %%p
        echo 📁 Criada pasta: %%p
    ) else (
        echo ✔ Pasta existente: %%p
    )
)

echo.

:: --------------------------------------------
:: Criar atalho na área de trabalho
:: --------------------------------------------
echo 🔗 Criando atalho na área de trabalho...

set SHORTCUT="%USERPROFILE%\Desktop\APEX Dashboard.lnk"
set TARGET="%cd%\apex_supervisor.py"

powershell -command ^
 "$s=(New-Object -COM WScript.Shell).CreateShortcut(%SHORTCUT%); ^
  $s.TargetPath='python'; ^
  $s.Arguments=%TARGET%; ^
  $s.WorkingDirectory='%cd%'; ^
  $s.Save()"

echo ✅ Atalho criado na área de trabalho!
echo.

:: --------------------------------------------
:: Finalização
:: --------------------------------------------
echo ============================================
echo 🎉 Instalação concluída com sucesso!
echo ============================================
echo.
echo 👉 Para iniciar o APEX:
echo     python apex_supervisor.py
echo.
echo 👉 Para iniciar o Dashboard Avançado:
echo     python dashboard.py
echo.
echo ============================================
echo Pressione qualquer tecla para sair...
pause > nul
exit /b 0

:error
echo.
echo ❌ O instalador encontrou um erro crítico.
echo 💡 Revise as mensagens acima e tente novamente.
echo.
pause
exit /b 1