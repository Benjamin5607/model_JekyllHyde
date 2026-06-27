# LoRA Fine-tuning Pipeline

Fine-tune Jekyll & Hyde on Gemma bases (not training from scratch).

## Supported bases

| Key | Ollama | HuggingFace | VRAM |
|---|---|---|---|
| gemma2-2b | gemma2:2b | google/gemma-2-2b-it | ~8GB |
| gemma2-9b | gemma2:9b | google/gemma-2-9b-it | ~24GB |
| gemma3-4b | gemma3:4b | google/gemma-3-4b-it | ~12GB |
| gemma3-12b | gemma3:12b | google/gemma-3-12b-it | ~32GB |

## Dual LoRA architecture

| Adapter | Path | Used when |
|---------|------|-----------|
| Jekyll | `models/adapters/jekyll-lora` | Defense, policy, chat (default) |
| Hyde | `models/adapters/hyde-lora` | Red-team, duel Hyde turns |

Runtime loads **one 4-bit base** + both adapters; `set_adapter()` switches per request.
Legacy single adapter (`jekyll-hyde-lora`) bootstraps both if missing:

```bash
python training/bootstrap_adapters.py
```

## Pipeline

```bash
# 1. Prepare JSONL from guidelines + probes
python training/prepare_dataset.py --guidelines data/community_guidelines.md

# 2. Install training deps (GPU required)
pip install -e ".[train]"

# 3. Validate config
python training/train_lora.py --dry-run --base gemma2-2b --persona both

# 4. Train both persona adapters (QLoRA 4-bit base frozen)
python training/train_lora.py --base gemma2-2b --4bit --persona both

# 5. Merge Jekyll snapshot for GGUF/Ollama + register Ollama
python training/merge_and_export.py --base gemma2-2b --persona jekyll --ollama

# 6. Optional GGUF export (llama.cpp)
python training/quantize_export.py
```

Continuous learning (`config/learning.yaml`) runs steps 4–6 automatically when curated data reaches 20 samples.

## HuggingFace access

1. **라이선스 동의** — huggingface.co Gemma 모델 페이지에서 Agree
2. **토큰 로그인**

```powershell
.venv-train\Scripts\python.exe -m huggingface_hub.cli login
```

## 한 번에 LoRA 학습

```powershell
scripts\train_lora.bat
```

RTX 5060 Ti 16GB → **gemma2-2b** 권장
