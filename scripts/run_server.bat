@echo off
chcp 65001 >nul 2>&1
setlocal EnableExtensions
title Jekyll ^& Hyde Server

cd /d "%~dp0.."
set "ROOT=%CD%"
set "PORT=8080"

set "PYTHON="
if exist "%ROOT%\.venv-train\Scripts\python.exe" if exist "%ROOT%\models\merged\jekyll-hyde\config.json" (
  set "PYTHON=%ROOT%\.venv-train\Scripts\python.exe"
)
if not defined PYTHON if exist "%ROOT%\.venv\Scripts\python.exe" set "PYTHON=%ROOT%\.venv\Scripts\python.exe"
if not defined PYTHON (
  echo [ERROR] Python not found.
  pause
  exit /b 1
)

set "HF_HUB_DISABLE_PROGRESS_BARS=1"
set "TRANSFORMERS_NO_ADVISORY_WARNINGS=1"
set "TOKENIZERS_PARALLELISM=false"

if exist "%ROOT%\secrets\hf_token.txt" (
  for /f "usebackq delims=" %%T in ("%ROOT%\secrets\hf_token.txt") do set "HF_TOKEN=%%T"
)

echo ========================================
echo  Jekyll ^& Hyde Server
echo  http://127.0.0.1:%PORT%
echo  DO NOT CLOSE - server runs in this window
echo  Stop: Ctrl+C
echo ========================================
echo.

"%PYTHON%" -m safety_eval.platform.serve --port %PORT%

echo.
echo Server stopped.
pause
