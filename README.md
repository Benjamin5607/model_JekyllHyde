# Jekyll & Hyde — `model_JekyllHyde`

**Independent dual-persona LLM** (Gemma 2 2B + **dual LoRA adapters**) with a self-hosted chat platform, MCP guidelines, structured responses, domain specialization, and continuous learning.

---

## Download install package (recommended)

Download **all files** from [Release v1.2.3](https://github.com/Benjamin5607/model_JekyllHyde/releases/tag/v1.2.3):

| File | Purpose |
|------|---------|
| [JekyllHyde-1.2.3-app.zip](https://github.com/Benjamin5607/model_JekyllHyde/releases/download/v1.2.3/JekyllHyde-1.2.3-app.zip) | Platform, scripts, configs |
| [model.part00–02.gz](https://github.com/Benjamin5607/model_JekyllHyde/releases/tag/v1.2.3) | Model weights (gzip L9, 3 parts) |

1. Extract **app.zip** → run **`install.bat`** (with `.gz` parts in same folder) → **http://127.0.0.1:8080**

**Requirements:** Windows 10/11 · Python 3.10+ · NVIDIA GPU 8 GB+ VRAM recommended

---

## Project structure

```
model_JekyllHyde/
├── safety_eval/           # Core platform
│   ├── platform/          # Engine, duel, UI server, formats
│   ├── quant/             # Market data, pipeline, research
│   ├── specialization/    # Domain detection (quant/policy/gray/hardening)
│   ├── learning/          # Data diet, curator, continuous train pipeline
│   ├── storage/           # Optimizer + release packager
│   ├── verification/      # Free API cross-check providers
│   └── mcp/               # Cursor MCP server
├── training/              # LoRA dataset, train, merge
├── models/
│   ├── merged/jekyll-hyde/   # Fine-tuned weights (download via Releases)
│   └── adapters/             # jekyll-lora + hyde-lora (runtime switching)
├── config/                # Platform, storage, specialization YAML
├── data/                  # Guidelines probes, learning queue
├── scripts/               # start/stop, install, build_release, verify
└── dist/                  # Release artifacts (local build; auto-pruned)
```

**Not in repo (by design):** `model.safetensors` (~5 GB), `secrets/`, `.venv*`, old `dist/` builds.

---

## Features

| Feature | Description |
|---------|-------------|
| **Chat + investment memo** | 5-stage pipeline: live data → per-section LLM → assemble |
| **Duel** | Auto-routes: **equity** (market debate) · **guideline** (MCP red-team) · **debate** (any topic → middle ground) |
| **Guideline / gray-zone / hardening** | Slim persona routing + **Jekyll/Hyde LoRA switch** |
| **Learning** | Data diet → dual QLoRA updates → auto GGUF export (llama.cpp) |

### Data diet (efficiency)

- **Semantic dedup:** bge-small embeddings; cosine ≥ 0.92 rejects near-duplicates (not just hash)
- **Balancing:** FIFO caps per category & persona; max 2,000 curated records
- **Compact prompts:** slim Jekyll/Hyde routing + compact quant digest (fewer tokens)
- **Run cleanup:** `python scripts\data_diet.py`

### Dual LoRA + GGUF pipeline (v1.2.3+)

- **Runtime:** 4-bit frozen Gemma base + `jekyll-lora` / `hyde-lora` hot-swap per request
- **Training:** `train_lora.py --persona both` filters dataset by persona bucket
- **Deploy snapshot:** merge Jekyll adapter → optional GGUF Q4_K_M after each continuous-learning cycle
- **Bootstrap:** legacy `jekyll-hyde-lora` auto-copies to both adapters if missing

### Duel routing

| Kind | Trigger | Outcome |
|------|---------|---------|
| Equity | Finance query + live data | Bear case ↔ defense → gray zones + middle ground |
| Guideline | MCP guidelines + policy topic | Hyde probes ↔ Jekyll verdict + verification |
| Debate | Any other topic | Opposing views → final **Middle ground** synthesis |

---

## Run from source

```powershell
git clone https://github.com/Benjamin5607/model_JekyllHyde.git
cd model_JekyllHyde
pip install -e ".[train,quant,mcp]"
scripts\start.bat
```

Verify: `python scripts\verify_today.py` · Data diet: `python scripts\data_diet.py`

Storage cleanup (rotates logs, semantic dedupe, prunes old dist/checkpoints):

```powershell
python -m safety_eval.storage.optimizer
```

---

## Build release (maintainers)

```powershell
scripts\build_release.ps1
```

Output: `dist/JekyllHyde-1.2.3-app.zip` + `model.partXX.gz` + manifest.

---

## Release history

| Tag | Notes |
|-----|-------|
| v1.2.3 | [Dual LoRA + auto GGUF](https://github.com/Benjamin5607/model_JekyllHyde/releases/tag/v1.2.3) |
| [v1.2.2](https://github.com/Benjamin5607/model_JekyllHyde/releases/tag/v1.2.2) | Data diet, semantic dedup, slim routing, compact quant |
| [v1.2.1](https://github.com/Benjamin5607/model_JekyllHyde/releases/tag/v1.2.1) | Structure cleanup, dist auto-prune |
| [v1.2.0](https://github.com/Benjamin5607/model_JekyllHyde/releases/tag/v1.2.0) | Duel middle-ground synthesis |
| [v1.1.0](https://github.com/Benjamin5607/model_JekyllHyde/releases/tag/v1.1.0) | 5-stage investment memo pipeline |
| [v1.0.0](https://github.com/Benjamin5607/model_JekyllHyde/releases/tag/v1.0.0) | Initial release |

---

## License

- **Code:** MIT — [LICENSE](LICENSE)
- **Model:** [Gemma 2](https://huggingface.co/google/gemma-2-2b-it) — [Gemma Terms](https://ai.google.dev/gemma/terms)
