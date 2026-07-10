"""Differential-privacy helpers for LoRA / DPO training (DP-SGD noise injection)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "learning.yaml"


def load_dp_cfg() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return (yaml.safe_load(f) or {}).get("privacy", {}).get("dp_sgd", {})


@dataclass
class DpSgdConfig:
    enabled: bool = False
    noise_multiplier: float = 1.1
    max_grad_norm: float = 1.0
    target_epsilon: float = 8.0
    target_delta: float = 1e-5

    @classmethod
    def from_yaml(cls) -> DpSgdConfig:
        raw = load_dp_cfg()
        return cls(
            enabled=bool(raw.get("enabled", False)),
            noise_multiplier=float(raw.get("noise_multiplier", 1.1)),
            max_grad_norm=float(raw.get("max_grad_norm", 1.0)),
            target_epsilon=float(raw.get("target_epsilon", 8.0)),
            target_delta=float(raw.get("target_delta", 1e-5)),
        )


def apply_dp_to_trainer(trainer: Any, cfg: DpSgdConfig | None = None) -> str:
    """Attach Opacus DP-SGD when available; else clip grads + Gaussian noise hook."""
    cfg = cfg or DpSgdConfig.from_yaml()
    if not cfg.enabled:
        return "dp_disabled"

    try:
        from opacus import PrivacyEngine

        engine = PrivacyEngine()
        model, optimizer, train_loader = engine.make_private(
            module=trainer.model,
            optimizer=trainer.optimizer,
            data_loader=trainer.get_train_dataloader(),
            noise_multiplier=cfg.noise_multiplier,
            max_grad_norm=cfg.max_grad_norm,
        )
        trainer.model = model
        trainer.optimizer = optimizer
        return f"opacus_dp noise={cfg.noise_multiplier} clip={cfg.max_grad_norm}"
    except ImportError:
        pass

    # Lightweight fallback: gradient clipping only (document as partial DP)
    import torch

    def _clip_hook(grad: torch.Tensor) -> torch.Tensor:
        norm = grad.norm(2)
        if norm > cfg.max_grad_norm:
            grad = grad * (cfg.max_grad_norm / (norm + 1e-6))
        if cfg.noise_multiplier > 0:
            noise = torch.randn_like(grad) * cfg.noise_multiplier * cfg.max_grad_norm / math.sqrt(grad.numel())
            grad = grad + noise
        return grad

    for p in trainer.model.parameters():
        if p.requires_grad:
            p.register_hook(_clip_hook)
    return f"fallback_dp noise={cfg.noise_multiplier} clip={cfg.max_grad_norm}"
