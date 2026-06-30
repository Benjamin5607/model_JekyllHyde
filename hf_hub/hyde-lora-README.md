---
license: gemma
base_model: google/gemma-2-2b-it
tags:
  - lora
  - gemma2
  - jekyll-hyde
  - red-team
library_name: peft
---

# Hyde LoRA — red-team / gray-zone probe persona

Part of [Jekyll & Hyde](https://github.com/Benjamin5607/model_JekyllHyde) (v1.5).

| | |
|---|---|
| **Base** | [google/gemma-2-2b-it](https://huggingface.co/google/gemma-2-2b-it) |
| **Pair adapter** | [jekyll-lora](https://huggingface.co/benjamin5607/jekyll-hyde-jekyll-lora) |
| **Demo Space** | [jekyll-hyde-demo](https://huggingface.co/spaces/benjamin5607/jekyll-hyde-demo) |

## Load

```python
from peft import PeftModel
from transformers import AutoModelForCausalLM

base = AutoModelForCausalLM.from_pretrained("google/gemma-2-2b-it")
model = PeftModel.from_pretrained(base, "benjamin5607/jekyll-hyde-hyde-lora")
```

Blend with Jekyll via `add_weighted_adapter` (MoE) — see project docs.

## License

Gemma [terms](https://ai.google.dev/gemma/terms) apply. Project code: MIT.
