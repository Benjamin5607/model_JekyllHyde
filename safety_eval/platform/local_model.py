"""Load and run the fine-tuned Jekyll & Hyde model (merged LoRA weights)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
MERGED_DIR = ROOT / "models" / "merged" / "jekyll-hyde"
MANIFEST_PATH = MERGED_DIR / "jekyll_hyde_manifest.json"

_model = None
_tokenizer = None
_load_error: str | None = None
_loading = False


def is_loaded() -> bool:
    return _model is not None and _tokenizer is not None


def is_loading() -> bool:
    return _loading


def load_error() -> str | None:
    return _load_error


@dataclass(frozen=True)
class LocalModelInfo:
    name: str
    display_name: str
    available: bool
    fine_tuned: bool
    base: str
    backend: str
    params_b: int | None = None
    method: str = "lora-merge"


def merged_model_available() -> bool:
    return (MERGED_DIR / "config.json").exists()


def read_manifest() -> dict[str, Any]:
    if MANIFEST_PATH.exists():
        with MANIFEST_PATH.open(encoding="utf-8") as f:
            return json.load(f)
    if merged_model_available():
        return {
            "name": "jekyll-hyde",
            "display_name": "Jekyll & Hyde",
            "fine_tuned": True,
            "base_huggingface": "google/gemma-2-2b-it",
            "base_key": "gemma2-2b",
            "method": "lora-merge",
            "params_b": 2,
        }
    return {}


def get_local_model_info() -> LocalModelInfo:
    manifest = read_manifest()
    if not merged_model_available():
        return LocalModelInfo(
            name="jekyll-hyde",
            display_name="Jekyll & Hyde",
            available=False,
            fine_tuned=False,
            base="",
            backend="local",
        )
    return LocalModelInfo(
        name=manifest.get("name", "jekyll-hyde"),
        display_name=manifest.get("display_name", "Jekyll & Hyde"),
        available=_load_error is None or _model is not None,
        fine_tuned=True,
        base=manifest.get("base_huggingface", manifest.get("base", "gemma")),
        backend="local",
        params_b=manifest.get("params_b"),
        method=manifest.get("method", "lora-merge"),
    )


def normalize_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    """Gemma 2 chat templates reject system role; fold into first user turn."""
    system_parts: list[str] = []
    out: list[dict[str, str]] = []
    for msg in messages:
        if msg["role"] == "system":
            system_parts.append(msg["content"])
        else:
            out.append(dict(msg))
    if system_parts:
        prefix = "\n\n".join(system_parts)
        for i, msg in enumerate(out):
            if msg["role"] == "user":
                out[i] = {"role": "user", "content": f"{prefix}\n\n{msg['content']}"}
                break
    return out


_TURN_LEAK_MARKERS = (
    "<start_of_turn>",
    "<end_of_turn>",
    "\nuser\n",
    "\nmodel\n",
    "\nmodel ",
    "\nassistant\n",
)


def clean_generation(text: str) -> str:
    """Trim role leaks, turn markers, and repeated paragraphs from model output."""
    t = text.strip()
    if not t:
        return t

    lower = t.lower()
    for marker in _TURN_LEAK_MARKERS:
        idx = lower.find(marker.lower())
        if idx > 0:
            t = t[:idx].strip()
            lower = t.lower()

    lines: list[str] = []
    for line in t.splitlines():
        if line.strip().lower() in {"model", "user", "assistant"}:
            break
        lines.append(line)
    t = "\n".join(lines).strip()

    paras = [p.strip() for p in re.split(r"\n{2,}", t) if p.strip()]
    deduped: list[str] = []
    for p in paras:
        if not deduped or p != deduped[-1]:
            deduped.append(p)
    return "\n\n".join(deduped).strip()


def _ensure_loaded() -> tuple[Any, Any]:
    global _model, _tokenizer, _load_error

    if _model is not None and _tokenizer is not None:
        return _model, _tokenizer

    if not merged_model_available():
        raise RuntimeError(f"Fine-tuned model not found at {MERGED_DIR}. Run training/merge first.")

    try:
        import os

        os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
        os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")

        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    except ImportError as exc:
        _load_error = "Install training env: pip install -e '.[train]' (or use .venv-train)"
        raise RuntimeError(_load_error) from exc

    try:
        tokenizer = AutoTokenizer.from_pretrained(MERGED_DIR, trust_remote_code=True)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        if torch.cuda.is_available():
            quant = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
            )
            model = AutoModelForCausalLM.from_pretrained(
                MERGED_DIR,
                trust_remote_code=True,
                quantization_config=quant,
                device_map="auto",
            )
        else:
            model = AutoModelForCausalLM.from_pretrained(
                MERGED_DIR,
                trust_remote_code=True,
                torch_dtype=torch.float32,
                device_map="cpu",
            )

        model.eval()
        _model = model
        _tokenizer = tokenizer
        _load_error = None
        return _model, _tokenizer
    except Exception as exc:
        _load_error = str(exc)
        raise RuntimeError(f"Failed to load fine-tuned model: {exc}") from exc


def chat(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.7,
    max_new_tokens: int = 384,
) -> str:
    import torch

    model, tokenizer = _ensure_loaded()
    norm = normalize_messages(messages)
    prompt = tokenizer.apply_chat_template(norm, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt")
    device = next(model.parameters()).device
    inputs = {k: v.to(device) for k, v in inputs.items()}

    gen_kwargs: dict[str, Any] = {
        "max_new_tokens": max_new_tokens,
        "pad_token_id": tokenizer.pad_token_id or tokenizer.eos_token_id,
        "eos_token_id": tokenizer.eos_token_id,
    }
    if temperature > 0:
        gen_kwargs.update(
            do_sample=True,
            temperature=temperature,
            top_p=0.9,
            repetition_penalty=1.12,
            no_repeat_ngram_size=4,
        )
    else:
        gen_kwargs["do_sample"] = False

    with torch.no_grad():
        output = model.generate(**inputs, **gen_kwargs)

    new_tokens = output[0][inputs["input_ids"].shape[1] :]
    return clean_generation(tokenizer.decode(new_tokens, skip_special_tokens=True))


def reload_model() -> LocalModelInfo:
    """Unload and reload merged weights after incremental training."""
    global _model, _tokenizer, _load_error, _loading
    _model = None
    _tokenizer = None
    _load_error = None
    _loading = False
    return preload()


def preload() -> LocalModelInfo:
    """Warm up GPU weights (call from background thread)."""
    global _loading, _load_error
    if not merged_model_available():
        return get_local_model_info()
    if is_loaded():
        return get_local_model_info()
    _loading = True
    _load_error = None
    try:
        _ensure_loaded()
    except Exception as exc:
        _load_error = str(exc)
        raise
    finally:
        _loading = False
    return get_local_model_info()
