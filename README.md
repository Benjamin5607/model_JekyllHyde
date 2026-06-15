# Jekyll & Hyde — `model_JekyllHyde`

**Independent dual-persona LLM** (Gemma 2 2B + LoRA merge) with a self-hosted chat platform, MCP guidelines, structured responses, domain specialization, and continuous learning.

---

## Download install package (recommended)

All release assets use **maximum compression (level 9)**. Model parts are **gzip-compressed** for smaller downloads.

Download **all files** from [Release v1.2.0](https://github.com/Benjamin5607/model_JekyllHyde/releases/tag/v1.2.0):

| File | Purpose |
|------|---------|
| [JekyllHyde-1.2.0-app.zip](https://github.com/Benjamin5607/model_JekyllHyde/releases/download/v1.2.0/JekyllHyde-1.2.0-app.zip) | Platform, scripts, configs (ZIP deflate L9) |
| [model.part00.gz](https://github.com/Benjamin5607/model_JekyllHyde/releases/download/v1.2.0/JekyllHyde-1.2.0-model.part00.gz) | Model weights part 1/3 (gzip L9) |
| [model.part01.gz](https://github.com/Benjamin5607/model_JekyllHyde/releases/download/v1.2.0/JekyllHyde-1.2.0-model.part01.gz) | Model weights part 2/3 (gzip L9) |
| [model.part02.gz](https://github.com/Benjamin5607/model_JekyllHyde/releases/download/v1.2.0/JekyllHyde-1.2.0-model.part02.gz) | Model weights part 3/3 (gzip L9) |

**Local build:** `scripts\build_release.ps1` builds `JekyllHyde-1.2.0-win64.zip` with **live progress** during level-9 compression (~30–90 min for the 5 GB model).

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
| **Stock analysis** | Multi-stage investment memos with live Yahoo/FDR data (not financial advice) |
| **Guideline audit** | Section mapping, conflicts, clarity ratings, patch suggestions |
| **Gray-zone analysis** | Intent decomposition, allow/block/flag with dual reasoning |
| **Policy hardening** | Gap register, exploit scenarios, recommended rule text, validation probes |
| **Chat** | Sky-blue UI, multilingual (matches your message language) |
| **Jekyll** | Guideline defense, structured refusals |
| **Hyde** | Authorized red-team probes & gap finding |
| **Duel** | Hyde↔Jekyll debate with middle-ground synthesis (3 duel kinds) |
| **Learning** | Chat feedback → curated dataset → incremental LoRA retrain |

### Duel mode — three paths

Duel auto-routes by topic (Jekyll + Hyde toggles on):

| Kind | When | Behavior |
|------|------|----------|
| **Equity** | Investment/market query + live data | Hyde bear case ↔ Jekyll data-backed defense → **middle ground & gray zones** |
| **Guideline** | MCP guidelines active + policy topic | Hyde red-team probes ↔ Jekyll verdict + verification APIs |
| **Debate** | Any other topic, no MCP policy focus | Hyde opposes ↔ Jekyll defends → final round **Middle ground** synthesis |

Every duel round is adversarial but **converges**: concede valid points, narrow disagreements, close with shared truths and open questions.

### Chat — Investment memo pipeline (2B-aware)

For Korean/English equity memos in **Chat** mode, the platform runs a **5-stage pipeline**:

```
Stage 1 [CODE]  Collect live market data (Yahoo Finance, FDR)
Stage 2 [CODE]  Render locked facts (prices, quarters, headlines)
Stage 3 [LLM×N] Digest each headline → 2 sentences
Stage 4 [LLM×M] Analyze one section per call (7 sections)
Stage 5 [CODE]  Assemble final markdown + disclaimer
```

Cross-verify after install: `python scripts\verify_today.py`

---

## Run from source (developers)

```powershell
git clone https://github.com/Benjamin5607/model_JekyllHyde.git
cd model_JekyllHyde

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

```powershell
python -m safety_eval.storage.optimizer
```

API: `POST /api/storage/optimize` · `GET /api/storage/status`

---

## Continuous learning

```powershell
python training/continuous.py --curate-only
python training/continuous.py --train
```

At **20 curated samples**, background **2-epoch LoRA** + merge + hot reload.

---

## Build install ZIP (maintainers)

```powershell
scripts\build_release.ps1
```

Output: `dist/JekyllHyde-1.2.0-app.zip`, `dist/JekyllHyde-1.2.0-model.partXX.gz`, `dist/JekyllHyde-1.2.0-win64.zip`

```powershell
gh release upload v1.2.0 dist/JekyllHyde-1.2.0-app.zip dist/*.gz dist/*.manifest.json -R Benjamin5607/model_JekyllHyde --clobber
```

---

## Release history

| Tag | Notes |
|-----|-------|
| [v1.2.0](https://github.com/Benjamin5607/model_JekyllHyde/releases/tag/v1.2.0) | Duel middle-ground debate; equity/guideline/debate routing |
| [v1.1.0](https://github.com/Benjamin5607/model_JekyllHyde/releases/tag/v1.1.0) | 5-stage investment memo pipeline, domain specialization |
| [v1.0.0](https://github.com/Benjamin5607/model_JekyllHyde/releases/tag/v1.0.0) | Initial release, level-9 gzip packaging |

---

## License

- **Code:** MIT — see [LICENSE](LICENSE)
- **Model weights:** [Google Gemma 2](https://huggingface.co/google/gemma-2-2b-it) — [Gemma Terms of Use](https://ai.google.dev/gemma/terms)

---

## Ethics

For **your own systems** and authorized safety testing only.
