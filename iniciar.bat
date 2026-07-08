@echo off
title Gerenciador de Tarefas - Inicializador
cd /d "%~dp0"

echo ============================================
echo    Gerenciador de Tarefas - Iniciando...
echo ============================================
echo.

REM 1) Garante que o ambiente virtual do back-end existe
if not exist "backend\.venv\Scripts\python.exe" (
    echo [1/4] Criando ambiente virtual do back-end...
    python -m venv backend\.venv
    if errorlevel 1 (
        echo.
        echo ERRO: Python nao encontrado. Instale o Python em https://python.org e tente de novo.
        pause
        exit /b 1
    )
    echo [2/4] Instalando dependencias ^(so na primeira vez^)...
    backend\.venv\Scripts\python.exe -m pip install -q -r backend\requirements.txt
) else (
    echo [1/4] Ambiente virtual encontrado.
    echo [2/4] Dependencias ja instaladas.
)

REM 2) Sobe o back-end (API Flask, porta 5000) em uma janela propria
echo [3/4] Iniciando o back-end em http://127.0.0.1:5000 ...
start "Back-end - API Flask (nao feche esta janela)" /d "%~dp0backend" cmd /k ".venv\Scripts\python.exe app.py"

REM 3) Sobe o front-end (servidor estatico, porta 8080) em outra janela
echo [4/4] Iniciando o front-end em http://127.0.0.1:8080 ...
start "Front-end - Gerenciador de Tarefas (nao feche esta janela)" /d "%~dp0frontend" cmd /k "..\backend\.venv\Scripts\python.exe -m http.server 8080"

REM 4) Aguarda os servidores subirem e abre o navegador
timeout /t 3 /nobreak >nul
start http://127.0.0.1:8080

echo.
echo Pronto! O projeto abriu no navegador: http://127.0.0.1:8080
echo Para encerrar, feche as duas janelas de servidor que foram abertas.
echo.
timeout /t 6 >nul
