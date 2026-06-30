---
license: gemma
base_model: google/gemma-2-2b-it
tags:
  - lora
  - gemma2
  - jekyll-hyde
  - safety
  - red-team
library_name: peft
---

# Jekyll LoRA — guideline defense persona

Part of [Jekyll & Hyde](https://github.com/Benjamin5607/model_JekyllHyde) (v1.5).

| | |
|---|---|
| **Base** | [google/gemma-2-2b-it](https://huggingface.co/google/gemma-2-2b-it) |
| **Pair adapter** | [hyde-lora](https://huggingface.co/Benjamin5607/jekyll-hyde-hyde-lora) |
| **Demo Space** | [jekyll-hyde-demo](https://huggingface.co/spaces/Benjamin5607/jekyll-hyde-demo) |

## Load

```python
from peft import PeftModel
from transformers import AutoModelForCausalLM

base = AutoModelForCausalLM.from_pretrained("google/gemma-2-2b-it")
model = PeftModel.from_pretrained(base, "Benjamin5607/jekyll-hyde-jekyll-lora")
```

Use with Hyde adapter for MoE blending — see project `safety_eval/platform/local_model.py`.

## License

Gemma [terms](https://ai.google.dev/gemma/terms) apply to the base model. Project code: MIT.
