@echo off
chcp 65001 >nul
title JULIANA - Gestao Clinica

:: Ir para a pasta do script
cd /d "%~dp0"

echo ======================================================================
echo  JULIANA - Sistema de Gestao Clinica
echo ======================================================================
echo.
echo  Iniciando sistema...
echo.
echo  Credenciais de acesso:
echo    Usuario: admin
echo    Senha: admin123
echo.
echo  Preparando ambiente virtual (venv)...

:: Variaveis de ambiente para Unicode e cliente Postgres
set "PGCLIENTENCODING=UTF8"
set "PYTHONIOENCODING=utf-8"

:: Criar venv se nao existir (uso de labels para evitar sintaxe complexa)
if not exist ".venv\Scripts\python.exe" goto MAKE_VENV
goto HAVE_VENV

:MAKE_VENV
where py >nul 2>nul
if errorlevel 1 (
  python -m venv .venv
) else (
  rem tenta py 3.12, depois py 3.x e por fim python
  py -3.12 -m venv .venv 2>nul || py -3 -m venv .venv 2>nul || python -m venv .venv
)

:HAVE_VENV

set "PYVENV=.venv\Scripts\python.exe"
if not exist "%PYVENV%" (
	echo [ERRO] Nao foi possivel criar/encontrar a venv. Verifique se o Python 3 esta instalado.
	pause
	exit /b 1
)

:: Garantir pip atualizado e dependencias instaladas (somente se streamlit nao estiver presente)
"%PYVENV%" -m pip --disable-pip-version-check install --upgrade pip setuptools wheel >nul
if not exist ".venv\Scripts\streamlit.exe" (
	echo Instalando dependencias (requirements.txt)...
	if not exist "logs" mkdir logs >nul 2>nul
	"%PYVENV%" -m pip --disable-pip-version-check install -r requirements.txt 1>"logs\pip_install.log" 2>&1
	if errorlevel 1 (
		echo [AVISO] Falha ao instalar dependencias. Veja logs\pip_install.log. Tentando continuar mesmo assim...
	) else (
		echo Dependencias instaladas com sucesso.
	)
)

:: Detectar porta livre a partir da 8510
set PORT=8510
:checkport
rem Procura linha em LISTENING para a porta alvo
netstat -ano | findstr /R /C:":%PORT% .*LISTENING" >nul
if %ERRORLEVEL%==0 (
	echo [AVISO] Porta %PORT% em uso. Tentando proxima...
	set /a PORT=%PORT%+1
	if %PORT% LSS 8530 goto checkport
)

echo.
echo  Abrindo em: http://localhost:%PORT%
echo  (Se o navegador nao abrir automaticamente, copia e cole a URL acima.)
echo.

:: Iniciar o Streamlit em uma nova janela e abrir o navegador padrao
start "JULIANA - Streamlit" "%PYVENV%" -m streamlit run app.py --server.port=%PORT% --server.headless=false
timeout /t 2 /nobreak >nul
start "" "http://localhost:%PORT%"

echo.
echo ======================================================================
echo  Aplicacao encerrada. Pressione uma tecla para sair.
echo ======================================================================
pause
