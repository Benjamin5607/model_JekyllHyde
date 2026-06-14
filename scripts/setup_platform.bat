@echo off
setlocal EnableExtensions
cd /d "%~dp0.."
set "ROOT=%CD%"

echo === Jekyll ^& Hyde Platform Setup ===

set "PYTHON="
if exist "%ROOT%\.venv-train\Scripts\python.exe" set "PYTHON=%ROOT%\.venv-train\Scripts\python.exe"
if not defined PYTHON if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PYTHON (
  for /f "delims=" %%P in ('py -3.12 -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON=%%P"
)
if not defined PYTHON (
  for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON=%%P"
)

if not defined PYTHON (
  echo Python 3.10+ required. Install from python.org or: winget install Python.Python.3.12
  pause
  exit /b 1
)

echo Python: %PYTHON%

if not exist "%ROOT%\.venv" (
  echo Creating .venv ...
  "%PYTHON%" -m venv "%ROOT%\.venv"
)
set "VENV=%ROOT%\.venv\Scripts\python.exe"
"%VENV%" -m pip install -U pip wheel
"%VENV%" -m pip install -e "%ROOT%[quant,mcp]"

echo.
echo Done. Double-click desktop shortcut or run: scripts\start.bat
pause
