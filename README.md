# Jekyll & Hyde — `model_JekyllHyde`

**Independent dual-persona LLM** (Gemma 2 2B + LoRA merge) with a self-hosted chat platform, MCP guidelines, structured responses, and continuous learning.

---

## Download install package (recommended)

GitHub limits single files to **2 GB**. Download **all files** from [Release v1.0.0](https://github.com/Benjamin5607/model_JekyllHyde/releases/tag/v1.0.0):

| File | Size | Purpose |
|------|------|---------|
| [JekyllHyde-1.0.0-app.zip](https://github.com/Benjamin5607/model_JekyllHyde/releases/download/v1.0.0/JekyllHyde-1.0.0-app.zip) | ~35 MB | Platform, scripts, configs |
| [JekyllHyde-1.0.0-model.part00](https://github.com/Benjamin5607/model_JekyllHyde/releases/download/v1.0.0/JekyllHyde-1.0.0-model.part00) | ~1.8 GB | Model weights (part 1/3) |
| [JekyllHyde-1.0.0-model.part01](https://github.com/Benjamin5607/model_JekyllHyde/releases/download/v1.0.0/JekyllHyde-1.0.0-model.part01) | ~1.8 GB | Model weights (part 2/3) |
| [JekyllHyde-1.0.0-model.part02](https://github.com/Benjamin5607/model_JekyllHyde/releases/download/v1.0.0/JekyllHyde-1.0.0-model.part02) | ~1.4 GB | Model weights (part 3/3) |

**Optional (local build only):** single `JekyllHyde-1.0.0-win64.zip` (~5 GB) via `scripts\build_release.ps1`

### Quick install (Windows)

1. Download **app.zip + all 3 model parts** into the same folder (e.g. `C:\JekyllHyde`).
2. Extract **app.zip**.
3. Copy **model.part00/01/02** into the extracted folder.
4. Run **`install.bat`** → merges model, creates venv, desktop shortcut.
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
# Output: dist/JekyllHyde-1.0.0-win64.zip + manifest JSON
```

Upload to GitHub Releases:

```powershell
gh release create v1.0.0 dist/JekyllHyde-1.0.0-win64.zip --title "JekyllHyde 1.0.0"
```

---

## Release history

| Tag | Files | Notes |
|-----|-------|-------|
| [v1.0.0](https://github.com/Benjamin5607/model_JekyllHyde/releases/tag/v1.0.0) | `app.zip` + `model.part00–02` | Platform + Gemma2-2B merged weights (split for GitHub 2GB limit) |

---

## License

- **Code:** MIT — see [LICENSE](LICENSE)
- **Model weights:** Derived from [Google Gemma 2](https://huggingface.co/google/gemma-2-2b-it) — subject to [Gemma Terms of Use](https://ai.google.dev/gemma/terms)

---

## Ethics

For **your own systems** and authorized safety testing only. Do not use Hyde probes against third-party services without permission.
