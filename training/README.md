# LoRA Fine-tuning Pipeline

Fine-tune Jekyll & Hyde on Gemma bases (not training from scratch).

## Supported bases

| Key | Ollama | HuggingFace | VRAM |
|---|---|---|---|
| gemma2-2b | gemma2:2b | google/gemma-2-2b-it | ~8GB |
| gemma2-9b | gemma2:9b | google/gemma-2-9b-it | ~24GB |
| gemma3-4b | gemma3:4b | google/gemma-3-4b-it | ~12GB |
| gemma3-12b | gemma3:12b | google/gemma-3-12b-it | ~32GB |

## Pipeline

```bash
# 1. Prepare JSONL from guidelines + probes
python training/prepare_dataset.py --guidelines data/community_guidelines.md

# 2. Install training deps (GPU required)
pip install -e ".[train]"

# 3. Validate config
python training/train_lora.py --dry-run --base gemma3-4b

# 4. Train LoRA
python training/train_lora.py --base gemma3-4b --4bit

# 5. Merge + register in Ollama as jekyll-hyde-ft
python training/merge_and_export.py --base gemma3-4b --ollama
```

Platform and Guidelines Chat auto-prefer `jekyll-hyde-ft` when available.

## HuggingFace access

1. **라이선스 동의** (완료) — huggingface.co에서 Gemma 모델 페이지에서 Agree
2. **토큰 로그인** (다음 단계) — 웹 동의만으로는 CLI 다운로드 불가

```powershell
cd c:\Users\User\evil_model
.venv-train\Scripts\python.exe -m huggingface_hub.cli login
```

토큰 발급: https://huggingface.co/settings/tokens (Read 권한)

또는 한 줄:

```powershell
.venv-train\Scripts\python.exe scripts\setup_training.py --hf-token hf_여기에토큰
```

## 한 번에 LoRA 학습 (환경 설치 후)

```powershell
cd c:\Users\User\evil_model
scripts\train_lora.bat
```

또는 수동:

```powershell
$py = ".venv-train\Scripts\python.exe"
& $py training\prepare_dataset.py
& $py training\train_lora.py --base gemma2-2b --4bit
& $py training\merge_and_export.py --base gemma2-2b --ollama
```

RTX 5060 Ti 16GB → **gemma2-2b** 권장 (gemma3-4b도 가능)

## Modelfile-only (no GPU)

```bash
python scripts/create_model.py --base gemma3-4b --list-bases
python scripts/create_model.py --base gemma3-4b
```
