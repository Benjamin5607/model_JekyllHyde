"""Gemma base model registry for Ollama and HuggingFace LoRA."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

CONFIG = Path(__file__).resolve().parent.parent.parent / "training" / "config.yaml"


@dataclass(frozen=True)
class BaseModelSpec:
    key: str
    ollama: str
    huggingface: str
    params_b: int
    vram_gb: int


def load_registry() -> dict[str, BaseModelSpec]:
    with CONFIG.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return {
        key: BaseModelSpec(key=key, **val)
        for key, val in cfg.get("base_models", {}).items()
    }


def get_base(key: str | None = None) -> BaseModelSpec:
    registry = load_registry()
    with CONFIG.open(encoding="utf-8") as f:
        default = yaml.safe_load(f).get("default_base", "gemma2-2b")
    key = key or default
    if key not in registry:
        raise KeyError(f"Unknown base '{key}'. Available: {list(registry)}")
    return registry[key]


def list_bases() -> list[dict]:
    return [
        {"key": s.key, "ollama": s.ollama, "huggingface": s.huggingface, "params_b": s.params_b, "vram_gb": s.vram_gb}
        for s in load_registry().values()
    ]
