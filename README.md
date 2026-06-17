# Jekyll & Hyde — `model_JekyllHyde`

**Independent dual-persona LLM** (Gemma 2 2B + LoRA merge) with a self-hosted chat platform, MCP guidelines, structured responses, domain specialization, and continuous learning.

---

## Download install package (recommended)

Download **all files** from [Release v1.2.1](https://github.com/Benjamin5607/model_JekyllHyde/releases/tag/v1.2.1):

| File | Purpose |
|------|---------|
| [JekyllHyde-1.2.1-app.zip](https://github.com/Benjamin5607/model_JekyllHyde/releases/download/v1.2.1/JekyllHyde-1.2.1-app.zip) | Platform, scripts, configs |
| [model.part00–02.gz](https://github.com/Benjamin5607/model_JekyllHyde/releases/tag/v1.2.1) | Model weights (gzip L9, 3 parts) |

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
│   ├── learning/          # Feedback → curated training
│   ├── storage/           # Optimizer + release packager
│   ├── verification/      # Free API cross-check providers
│   └── mcp/               # Cursor MCP server
├── training/              # LoRA dataset, train, merge
├── models/
│   ├── merged/jekyll-hyde/   # Fine-tuned weights (download via Releases)
│   └── adapters/             # LoRA adapter (training)
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
| **Guideline / gray-zone / hardening** | Domain-specialized prompts + LoRA |
| **Learning** | UI feedback → curated JSONL → incremental LoRA |

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

Verify: `python scripts\verify_today.py`

Storage cleanup (rotates logs, dedupes learning data, prunes old dist/checkpoints):

```powershell
python -m safety_eval.storage.optimizer
```

---

## Build release (maintainers)

```powershell
scripts\build_release.ps1
```

Output: `dist/JekyllHyde-1.2.1-app.zip` + `model.partXX.gz` + manifest. Optimizer removes stale `dist/` versions automatically.

---

## Release history

| Tag | Notes |
|-----|-------|
| [v1.2.1](https://github.com/Benjamin5607/model_JekyllHyde/releases/tag/v1.2.1) | Structure cleanup, dist auto-prune, removed dead code |
| [v1.2.0](https://github.com/Benjamin5607/model_JekyllHyde/releases/tag/v1.2.0) | Duel middle-ground synthesis |
| [v1.1.0](https://github.com/Benjamin5607/model_JekyllHyde/releases/tag/v1.1.0) | 5-stage investment memo pipeline |
| [v1.0.0](https://github.com/Benjamin5607/model_JekyllHyde/releases/tag/v1.0.0) | Initial release |

---

## License

- **Code:** MIT — [LICENSE](LICENSE)
- **Model:** [Gemma 2](https://huggingface.co/google/gemma-2-2b-it) — [Gemma Terms](https://ai.google.dev/gemma/terms)
