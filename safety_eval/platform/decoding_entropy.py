"""Dynamic decoding entropy — link MoE Jekyll/Hyde blend to temperature, top-p, min-p."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml

ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = ROOT / "config" / "learning.yaml"


@dataclass(frozen=True)
class DecodingParams:
    temperature: float
    top_p: float
    min_p: float
    profile: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "temperature": round(self.temperature, 3),
            "top_p": round(self.top_p, 3),
            "min_p": round(self.min_p, 3),
            "profile": self.profile,
        }


def _load_decoding_cfg() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return (yaml.safe_load(f) or {}).get("decoding", {})


def decoding_for_lora_mix(
    jekyll_w: float,
    hyde_w: float,
    *,
    base_temperature: float | None = None,
) -> DecodingParams:
    """
    Map blend ratio to decoding entropy.

    Pure Jekyll → low temperature (strict defense).
    Balanced gray-zone blend → higher temperature + wider min-p for creative middle-ground.
    """
    cfg = _load_decoding_cfg()
    if not cfg.get("dynamic_entropy", True):
        t = base_temperature if base_temperature is not None else 0.7
        return DecodingParams(t, 0.9, 0.05, "static")

    jw, hw = max(0.0, jekyll_w), max(0.0, hyde_w)
    if jw + hw <= 0:
        jw, hw = 1.0, 0.0
    else:
        s = jw + hw
        jw, hw = jw / s, hw / s

    grayness = 1.0 - abs(jw - hw)

    if jw >= 0.95:
        return DecodingParams(
            float(cfg.get("jekyll_temperature", 0.15)),
            float(cfg.get("jekyll_top_p", 0.85)),
            float(cfg.get("jekyll_min_p", 0.08)),
            "strict_jekyll",
        )
    if hw >= 0.95:
        return DecodingParams(
            float(cfg.get("hyde_temperature", 0.35)),
            float(cfg.get("hyde_top_p", 0.92)),
            float(cfg.get("hyde_min_p", 0.05)),
            "hyde_probe",
        )

    temp_lo = float(cfg.get("blend_temp_min", 0.2))
    temp_hi = float(cfg.get("blend_temp_max", 0.78))
    temperature = temp_lo + (temp_hi - temp_lo) * min(1.0, grayness * 1.25)

    top_p = float(cfg.get("blend_top_p_min", 0.88)) + 0.1 * grayness
    min_p = float(cfg.get("blend_min_p_min", 0.06)) + 0.14 * grayness

    if base_temperature is not None and not cfg.get("link_to_moe", True):
        temperature = base_temperature

    return DecodingParams(
        min(0.95, max(0.05, temperature)),
        min(0.99, max(0.5, top_p)),
        min(0.35, max(0.02, min_p)),
        f"blend_j{int(jw * 100)}_h{int(hw * 100)}",
    )


def apply_to_generation_kwargs(params: DecodingParams, gen_kwargs: dict[str, Any]) -> dict[str, Any]:
    """Merge decoding params into transformers generate() kwargs."""
    out = dict(gen_kwargs)
    if params.temperature <= 0.01:
        out["do_sample"] = False
        out.pop("temperature", None)
        out.pop("top_p", None)
        out.pop("min_p", None)
        return out
    out.update(
        do_sample=True,
        temperature=params.temperature,
        top_p=params.top_p,
    )
    if params.min_p > 0:
        out["min_p"] = params.min_p
    return out
