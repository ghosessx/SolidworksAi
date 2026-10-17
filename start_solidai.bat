@echo off
title SolidAI — Autonomous Parametric CAD Agent
cd /d "%~dp0"

:: 1. Check if Ollama models directory is set; default if not
if "%OLLAMA_MODELS%"=="" (
    if exist "D:\OllamaModels" (
        set OLLAMA_MODELS=D:\OllamaModels
    )
)

:: 2. Launch Ollama background server if not already running
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I /N "ollama.exe">NUL
if "%ERRORLEVEL%"=="1" (
    echo [SolidAI] Starting Ollama local background server...
    start /B "" ollama serve
    timeout /t 3 /nobreak >nul
)

:: 3. Launch SolidAI GUI
echo [SolidAI] Launching SolidAI GUI...
python SolidAI_GUI.py
if "%ERRORLEVEL%" NEQ "0" (
    echo [SolidAI Error] Application exited with error code %ERRORLEVEL%.
    pause
)
