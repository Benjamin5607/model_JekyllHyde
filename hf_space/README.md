---
title: Jekyll & Hyde
emoji: 🎭
colorFrom: green
colorTo: red
sdk: gradio
sdk_version: 4.44.0
app_file: app.py
pinned: false
license: mit
short_description: Dual-persona Gemma 2 2B + LoRA MoE — Jekyll defense & Hyde red-team
models:
  - google/gemma-2-2b-it
  - Benjamin5607/jekyll-hyde-jekyll-lora
  - Benjamin5607/jekyll-hyde-hyde-lora
---

# Jekyll & Hyde — Hugging Face Demo

Browser demo of **Jekyll & Hyde** (Gemma 2 2B + dual LoRA, MoE blend, dynamic decoding).

| Mode | Description |
|------|-------------|
| **Chat** | Auto MoE blend from prompt (gray-zone aware) |
| **Jekyll** | Guideline defense (strict, low temperature) |
| **Hyde** | Red-team probe |
| **Duel** | Hyde ↔ Jekyll rebuttal → middle-ground synthesis |

## Setup (maintainers)

1. Accept [Gemma 2 license](https://huggingface.co/google/gemma-2-2b-it) on your HF account.
2. Upload adapters: `python scripts/upload_hf_hub.py`
3. Create this Space from the GitHub repo with **App file** = `hf_space/app.py` (or duplicate `hf_space/` into a dedicated Space repo).
4. Space **Settings → Hardware**: `T4 small` or enable **ZeroGPU** (CPU is very slow for 4-bit inference).
5. Add Space secret `HF_TOKEN` if gated model access fails (usually auto on Spaces).

## Local smoke test

```bash
pip install -r hf_space/requirements.txt
set HF_JEKYLL_ADAPTER=Benjamin5607/jekyll-hyde-jekyll-lora
set HF_HYDE_ADAPTER=Benjamin5607/jekyll-hyde-hyde-lora
python hf_space/app.py
```

Full platform (MCP, Workforce, learning): [GitHub — model_JekyllHyde](https://github.com/Benjamin5607/model_JekyllHyde)
