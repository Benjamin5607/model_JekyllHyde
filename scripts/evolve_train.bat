@echo off
chcp 65001 >nul
cd /d %~dp0..
set VENV=.venv-train\Scripts\python.exe
if not exist %VENV% (
  echo Run setup first: scripts\setup_training.py
  exit /b 1
)
echo [1/3] Curate chat feedback into training set...
%VENV% training\continuous.py --curate-only
echo [2/3] Merge dataset (base + curated + format gold)...
%VENV% training\continuous.py --merge-only
echo [3/3] Incremental LoRA train + merge + hot reload...
%VENV% training\continuous.py --train
echo Continuous learning cycle done.
pause
