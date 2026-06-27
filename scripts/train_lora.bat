@echo off
REM HuggingFace login + LoRA train (run after Gemma license accepted)
cd /d %~dp0..
set VENV=.venv-train\Scripts\python.exe
if not exist %VENV% (
  echo Run setup first: scripts\setup_training.py
  exit /b 1
)
echo Step 1: HuggingFace login (uses secrets\hf_token.txt if present)
if exist secrets\hf_token.txt (
  for /f "usebackq delims=" %%T in ("secrets\hf_token.txt") do set HF_TOKEN=%%T
  %VENV% -c "from huggingface_hub import login; import os; login(token=os.environ['HF_TOKEN'].strip(), add_to_git_credential=False)"
) else (
  echo Save token to secrets\hf_token.txt or run: scripts\setup_training.py --hf-token hf_xxxx
  exit /b 1
)
echo Step 2: Test Gemma access
%VENV% -c "from huggingface_hub import hf_hub_download; print(hf_hub_download('google/gemma-2-2b-it','config.json'))"
echo Step 3: Dataset
%VENV% training\prepare_dataset.py
echo Step 4: Dual LoRA train (Jekyll + Hyde adapters)
%VENV% training\train_lora.py --base gemma2-2b --4bit --persona both
echo Step 5: Merge Jekyll snapshot + optional Ollama
%VENV% training\merge_and_export.py --base gemma2-2b --persona jekyll --ollama
echo Step 6: GGUF export (if llama.cpp installed)
%VENV% training\quantize_export.py
echo Done.
