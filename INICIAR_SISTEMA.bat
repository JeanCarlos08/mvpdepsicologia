@echo off
chcp 65001 >nul
title JULIANA - Gestao Clinica

echo ======================================================================
echo  JULIANA - Sistema de Gestao Clinica
echo ======================================================================
echo.
echo  Iniciando sistema...
echo  Aguarde o navegador abrir automaticamente
echo.
echo  Credenciais:
echo    Usuario: admin
echo    Senha: admin123
echo.
echo  URL: http://localhost:8510
echo ======================================================================
echo.

cd /d "%~dp0"
set PGCLIENTENCODING=UTF8
set PYTHONIOENCODING=utf-8

python -m streamlit run core/app.py

pause
