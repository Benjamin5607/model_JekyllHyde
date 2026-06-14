# Jekyll & Hyde — `model_JekyllHyde`

**Independent dual-persona LLM** (Gemma 2 2B + LoRA merge) with a self-hosted chat platform, MCP guidelines, structured responses, and continuous learning.

---

## Download install package (recommended)

All release assets use **maximum compression (level 9)**. Model parts are **gzip-compressed** for smaller downloads.

Download **all files** from [Release v1.0.0](https://github.com/Benjamin5607/model_JekyllHyde/releases/tag/v1.0.0):

| File | Purpose |
|------|---------|
| [JekyllHyde-1.0.0-app.zip](https://github.com/Benjamin5607/model_JekyllHyde/releases/download/v1.0.0/JekyllHyde-1.0.0-app.zip) | Platform, scripts, configs (ZIP deflate L9) |
| [model.part00.gz](https://github.com/Benjamin5607/model_JekyllHyde/releases/download/v1.0.0/JekyllHyde-1.0.0-model.part00.gz) | Model weights part 1/3 (gzip L9) |
| [model.part01.gz](https://github.com/Benjamin5607/model_JekyllHyde/releases/download/v1.0.0/JekyllHyde-1.0.0-model.part01.gz) | Model weights part 2/3 (gzip L9) |
| [model.part02.gz](https://github.com/Benjamin5607/model_JekyllHyde/releases/download/v1.0.0/JekyllHyde-1.0.0-model.part02.gz) | Model weights part 3/3 (gzip L9) |

**Local build:** `scripts\build_release.ps1` builds `JekyllHyde-1.0.0-win64.zip` with **live progress** during level-9 compression (~30–90 min for the 5 GB model).

### Quick install (Windows)

1. Download **app.zip + 3× model.partXX.gz** from Releases.
2. Extract **app.zip** (e.g. `C:\JekyllHyde`).
3. Copy **`.gz` model parts** into the same folder.
4. Run **`install.bat`** → decompresses & merges model, creates venv, desktop shortcut.
5. Open **http://127.0.0.1:8080**

**Requirements:** Windows 10/11 · Python 3.10+ · NVIDIA GPU 8 GB+ VRAM recommended

---

## What you get

| Feature | Description |
|---------|-------------|
| **Chat** | Sky-blue UI, multilingual (matches your message language) |
| **Jekyll** | Guideline defense, structured refusals |
| **Hyde** | Authorized red-team probes |
| **Duel** | Hyde↔Jekyll debate or MCP guideline stress-test |
| **Quant** | Live market context (Korea, US, etc.) |
| **Formats** | Reports, tables, SWOT, how-to, market analysis (Markdown) |
| **Learning** | Chat feedback → curated dataset → incremental LoRA retrain |
| **Storage opt** | Auto gzip archives, dedupe, log rotation, checkpoint prune |

---

## Run from source (developers)

```powershell
git clone https://github.com/Benjamin5607/model_JekyllHyde.git
cd model_JekyllHyde

# Download model weights into models/merged/jekyll-hyde/ OR use release ZIP
pip install -e ".[train,quant,mcp]"
scripts\start.bat
```

Platform: **http://127.0.0.1:8080**

### MCP (Cursor)

```json
{
  "mcpServers": {
    "jekyll-hyde": {
      "command": "python",
      "args": ["-m", "safety_eval.mcp.server"],
      "cwd": "C:\\path\\to\\model_JekyllHyde"
    }
  }
}
```

Tools: `set_guidelines`, `chat_with_model`, `run_duel_verification`, `learning_status`, `run_continuous_learning`

---

## Storage optimization

Runs automatically every 60 minutes (and before incremental training):

- Rotates large `interactions.jsonl` → gzip archives under `data/archive/`
- Dedupes `curated_train.jsonl` by content hash
- Compresses oversized logs
- Prunes old LoRA checkpoints (keeps latest)

Manual run:

```powershell
python -m safety_eval.storage.optimizer
```

API: `POST /api/storage/optimize` · `GET /api/storage/status`

---

## Continuous learning

1. Good chat turns are scored and curated → `data/learning/curated_train.jsonl`
2. Thumbs up/down in UI adjusts training queue
3. At **20 curated samples**, background **2-epoch LoRA** + merge + hot reload
4. Manual cycle: `scripts\evolve_train.bat`

```powershell
python training/continuous.py --curate-only
python training/continuous.py --train
```

---

## Build install ZIP (maintainers)

```powershell
scripts\build_release.ps1
```

Shows **live progress** every 3 seconds while compressing at **level 9**:
- `dist/JekyllHyde-1.0.0-app.zip`
- `dist/JekyllHyde-1.0.0-win64.zip` (full single-file install)
- `dist/JekyllHyde-1.0.0-model.partXX.gz` (GitHub upload parts)

Replace GitHub release assets:

```powershell
gh release delete-asset v1.0.0 JekyllHyde-1.0.0-model.part00 -R Benjamin5607/model_JekyllHyde -y
# ... then upload:
gh release upload v1.0.0 dist/JekyllHyde-1.0.0-app.zip dist/*.gz dist/*.manifest.json -R Benjamin5607/model_JekyllHyde --clobber
```

---

## Release history

| Tag | Files | Notes |
|-----|-------|-------|
| [v1.0.0](https://github.com/Benjamin5607/model_JekyllHyde/releases/tag/v1.0.0) | `app.zip` + `model.part00–02.gz` | Level-9 compression; gzip model parts for GitHub |

---

## License

- **Code:** MIT — see [LICENSE](LICENSE)
- **Model weights:** Derived from [Google Gemma 2](https://huggingface.co/google/gemma-2-2b-it) — subject to [Gemma Terms of Use](https://ai.google.dev/gemma/terms)

---

## Ethics

For **your own systems** and authorized safety testing only. Do not use Hyde probes against third-party services without permission.
