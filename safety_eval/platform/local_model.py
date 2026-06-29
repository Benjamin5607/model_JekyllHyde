"""Load and run the fine-tuned Jekyll & Hyde model (dual LoRA or merged weights)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
MERGED_DIR = ROOT / "models" / "merged" / "jekyll-hyde"
MANIFEST_PATH = MERGED_DIR / "jekyll_hyde_manifest.json"
TRAIN_CONFIG = ROOT / "training" / "config.yaml"

AdapterName = Literal["jekyll", "hyde"]

_model = None
_tokenizer = None
_load_error: str | None = None
_loading = False
_backend: str = "none"
_active_adapter: str = "jekyll"
_base_model_id: str = "google/gemma-2-2b-it"
_last_bucket: str | None = None
_warmed_buckets: set[str] = set()


def _adapter_dirs() -> dict[AdapterName, Path]:
    defaults: dict[AdapterName, Path] = {
        "jekyll": ROOT / "models" / "adapters" / "jekyll-lora",
        "hyde": ROOT / "models" / "adapters" / "hyde-lora",
    }
    if TRAIN_CONFIG.exists():
        with TRAIN_CONFIG.open(encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        adapters = cfg.get("adapters") or {}
        for key in ("jekyll", "hyde"):
            rel = adapters.get(key)
            if rel:
                defaults[key] = ROOT / rel  # type: ignore[literal-required]
    return defaults


def _adapter_ready(path: Path) -> bool:
    return (path / "adapter_config.json").exists()


def dual_adapters_available() -> bool:
    dirs = _adapter_dirs()
    return _adapter_ready(dirs["jekyll"]) and _adapter_ready(dirs["hyde"])


def merged_model_available() -> bool:
    return (MERGED_DIR / "config.json").exists()


def model_weights_available() -> bool:
    return dual_adapters_available() or merged_model_available()


def is_loaded() -> bool:
    return _model is not None and _tokenizer is not None


def is_loading() -> bool:
    return _loading


def load_error() -> str | None:
    return _load_error


def backend_mode() -> str:
    return _backend


def active_adapter() -> AdapterName:
    return _active_adapter


def resolve_adapter(persona: str | None) -> AdapterName:
    focus = (persona or "balanced").lower()
    if focus == "hyde":
        return "hyde"
    return "jekyll"


@dataclass(frozen=True)
class LocalModelInfo:
    name: str
    display_name: str
    available: bool
    fine_tuned: bool
    base: str
    backend: str
    params_b: int | None = None
    method: str = "dual-lora"
    active_adapter: str = "jekyll"


def read_manifest() -> dict[str, Any]:
    if MANIFEST_PATH.exists():
        with MANIFEST_PATH.open(encoding="utf-8") as f:
            return json.load(f)
    if dual_adapters_available():
        return {
            "name": "jekyll-hyde",
            "display_name": "Jekyll & Hyde",
            "fine_tuned": True,
            "base_huggingface": _base_model_id,
            "base_key": "gemma2-2b",
            "method": "dual-lora",
            "params_b": 2,
        }
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
    if not model_weights_available():
        return LocalModelInfo(
            name="jekyll-hyde",
            display_name="Jekyll & Hyde",
            available=False,
            fine_tuned=False,
            base="",
            backend="local",
        )
    method = manifest.get("method", "dual-lora" if dual_adapters_available() else "lora-merge")
    return LocalModelInfo(
        name=manifest.get("name", "jekyll-hyde"),
        display_name=manifest.get("display_name", "Jekyll & Hyde"),
        available=_load_error is None or _model is not None,
        fine_tuned=True,
        base=manifest.get("base_huggingface", manifest.get("base", "gemma")),
        backend="local",
        params_b=manifest.get("params_b"),
        method=method,
        active_adapter=_active_adapter,
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
    """Trim role leaks, turn markers, repeated paragraphs, and template meta from model output."""
    from safety_eval.platform.output_guard import looks_like_template_leak

    t = text.strip()
    if not t:
        return t

    if looks_like_template_leak(t):
        for marker in (
            "Response Template",
            "RESPONSE TEMPLATE",
            "KEY CONCEPT",
            "Example Response Template",
            "SAMPLE ANSWER",
            "USER QUERY:",
        ):
            idx = t.find(marker)
            if idx >= 0:
                t = t[:idx].strip()
                break

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


def _load_dual_adapters() -> tuple[Any, Any]:
    global _backend, _active_adapter, _base_model_id

    import sys

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from training.bootstrap_adapters import bootstrap_dual_adapters

    bootstrap_dual_adapters()
    if not dual_adapters_available():
        raise RuntimeError("Dual LoRA adapters missing. Run training/train_lora.py --persona both")

    import os

    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    manifest = read_manifest()
    model_id = manifest.get("base_huggingface", _base_model_id)
    _base_model_id = model_id
    dirs = _adapter_dirs()

    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    if torch.cuda.is_available():
        quant = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
        )
        base = AutoModelForCausalLM.from_pretrained(
            model_id,
            trust_remote_code=True,
            quantization_config=quant,
            device_map="auto",
        )
    else:
        base = AutoModelForCausalLM.from_pretrained(
            model_id,
            trust_remote_code=True,
            torch_dtype=torch.float32,
            device_map="cpu",
        )

    model = PeftModel.from_pretrained(base, str(dirs["jekyll"]), adapter_name="jekyll")
    model.load_adapter(str(dirs["hyde"]), adapter_name="hyde")
    model.set_adapter("jekyll")
    model.eval()
    _backend = "dual-lora"
    _active_adapter = "jekyll"
    return model, tokenizer


def _load_merged() -> tuple[Any, Any]:
    global _backend

    import os

    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

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
    _backend = "merged"
    return model, tokenizer


def set_lora_mix(jekyll_w: float, hyde_w: float) -> None:
    """Blend jekyll + hyde LoRA adapters using pre-warmed MoE bucket pool."""
    global _active_adapter, _last_bucket

    if _model is None or _backend != "dual-lora":
        _set_active_adapter(resolve_adapter("hyde" if hyde_w > jekyll_w else "jekyll"))
        return

    from safety_eval.platform.lora_mix_cache import MOE_BUCKETS, record_mix_usage, snap_to_bucket

    snap = snap_to_bucket(jekyll_w, hyde_w)
    record_mix_usage(snap)

    if _last_bucket == snap.bucket_id:
        return

    if snap.adapter_name in ("jekyll", "hyde"):
        _model.set_adapter(snap.adapter_name)
        _active_adapter = snap.adapter_name  # type: ignore[assignment]
        _last_bucket = snap.bucket_id
        return

    try:
        if not _adapter_exists(snap.adapter_name):
            _model.add_weighted_adapter(
                adapters=["jekyll", "hyde"],
                weights=[snap.jekyll, snap.hyde],
                adapter_name=snap.adapter_name,
                combination_type="linear",
            )
            _warmed_buckets.add(snap.adapter_name)
        _model.set_adapter(snap.adapter_name)
        _active_adapter = snap.adapter_name  # type: ignore[assignment]
        _last_bucket = snap.bucket_id
    except Exception:
        _set_active_adapter("jekyll" if snap.jekyll >= snap.hyde else "hyde")
        _last_bucket = snap.bucket_id


def _adapter_exists(name: str) -> bool:
    if _model is None:
        return False
    return name in getattr(_model, "peft_config", {})


def prewarm_moe_buckets() -> int:
    """Pre-create all five MoE bucket adapters to avoid per-request overhead."""
    if _model is None or _backend != "dual-lora":
        return 0
    warmed = 0
    for name, jw, hw in MOE_BUCKETS:
        if _adapter_exists(name):
            _warmed_buckets.add(name)
            continue
        try:
            _model.add_weighted_adapter(
                adapters=["jekyll", "hyde"],
                weights=[jw, hw],
                adapter_name=name,
                combination_type="linear",
            )
            _warmed_buckets.add(name)
            warmed += 1
        except Exception:
            continue
    _model.set_adapter("jekyll")
    _active_adapter = "jekyll"
    return warmed


def _set_active_adapter(name: AdapterName) -> None:
    global _active_adapter
    if _model is None or _backend != "dual-lora":
        return
    _model.set_adapter(name)
    _active_adapter = name


def _ensure_loaded() -> tuple[Any, Any]:
    global _model, _tokenizer, _load_error

    if _model is not None and _tokenizer is not None:
        return _model, _tokenizer

    if not model_weights_available():
        raise RuntimeError(
            "Fine-tuned model not found. Run training/train_lora.py --persona both then merge."
        )

    try:
        import torch  # noqa: F401
        from transformers import AutoModelForCausalLM  # noqa: F401
    except ImportError as exc:
        _load_error = "Install training env: pip install -e '.[train]' (or use .venv-train)"
        raise RuntimeError(_load_error) from exc

    try:
        if dual_adapters_available():
            _model, _tokenizer = _load_dual_adapters()
        else:
            _model, _tokenizer = _load_merged()
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
    adapter: str | None = None,
    lora_mix: tuple[float, float] | None = None,
    grammar: str | None = None,
) -> str:
    import torch

    from safety_eval.platform.decoding_entropy import apply_to_generation_kwargs, decoding_for_lora_mix

    model, tokenizer = _ensure_loaded()
    mix_j, mix_h = 1.0, 0.0
    if lora_mix is not None:
        set_lora_mix(lora_mix[0], lora_mix[1])
        mix_j, mix_h = lora_mix[0], lora_mix[1]
    elif adapter:
        _set_active_adapter(resolve_adapter(adapter))
        mix_j = 1.0 if resolve_adapter(adapter) == "jekyll" else 0.0
        mix_h = 1.0 - mix_j

    decode = decoding_for_lora_mix(mix_j, mix_h, base_temperature=temperature)

    norm = normalize_messages(messages)
    prompt = tokenizer.apply_chat_template(norm, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt")
    device = next(model.parameters()).device
    inputs = {k: v.to(device) for k, v in inputs.items()}

    gen_kwargs: dict[str, Any] = {
        "max_new_tokens": max_new_tokens,
        "pad_token_id": tokenizer.pad_token_id or tokenizer.eos_token_id,
        "eos_token_id": tokenizer.eos_token_id,
        "repetition_penalty": 1.12,
        "no_repeat_ngram_size": 4,
    }
    gen_kwargs = apply_to_generation_kwargs(decode, gen_kwargs)

    if grammar == "mcp_tool_json":
        from safety_eval.platform.grammar_constraint import build_mcp_tool_prefix_fn

        gen_kwargs["prefix_allowed_tokens_fn"] = build_mcp_tool_prefix_fn(tokenizer)

    with torch.no_grad():
        output = model.generate(**inputs, **gen_kwargs)

    new_tokens = output[0][inputs["input_ids"].shape[1] :]
    return clean_generation(tokenizer.decode(new_tokens, skip_special_tokens=True))


def reload_model() -> LocalModelInfo:
    """Unload and reload weights after incremental training."""
    global _model, _tokenizer, _load_error, _loading, _backend, _active_adapter, _last_bucket, _warmed_buckets
    _model = None
    _tokenizer = None
    _load_error = None
    _loading = False
    _backend = "none"
    _active_adapter = "jekyll"
    _last_bucket = None
    _warmed_buckets = set()
    return preload()


def preload() -> LocalModelInfo:
    """Warm up GPU weights (call from background thread)."""
    global _loading, _load_error
    if not model_weights_available():
        return get_local_model_info()
    if is_loaded():
        return get_local_model_info()
    _loading = True
    _load_error = None
    try:
        _ensure_loaded()
        if _backend == "dual-lora":
            import threading

            threading.Thread(target=prewarm_moe_buckets, daemon=True).start()
    except Exception as exc:
        _load_error = str(exc)
        raise
    finally:
        _loading = False
    return get_local_model_info()
