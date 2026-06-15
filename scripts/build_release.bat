@echo off
chcp 65001 >nul
cd /d %~dp0..
echo Building Jekyll ^& Hyde install package (this may take several minutes)...
.venv-train\Scripts\python.exe -m safety_eval.storage.optimizer 2>nul
.venv-train\Scripts\python.exe -m safety_eval.storage.packager
if errorlevel 1 (
  python -m safety_eval.storage.packager
)
echo.
echo Output: dist\JekyllHyde-1.1.0-win64.zip
dir dist\*.zip
pause
