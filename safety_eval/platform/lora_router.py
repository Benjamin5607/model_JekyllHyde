"""Mixture-of-LoRA router — blend jekyll/hyde adapter weights by prompt character."""

from __future__ import annotations

import re
from dataclasses import dataclass

from safety_eval.platform.lora_mix_cache import snap_to_bucket

_GRAY = re.compile(r"\b(gray\s*zone|grey\s*zone|회색|borderline|middle\s*ground|미들|애매)\b", re.I)
_ATTACK = re.compile(
    r"\b(hyde|red[\s-]?team|probe|evasion|loophole|exploit|stress[\s-]?test|우회|허점)\b",
    re.I,
)
_DEFEND = re.compile(
    r"\b(jekyll|guideline|policy|moderation|block|refusal|audit|가이드|규칙|방어)\b",
    re.I,
)
_QUANT = re.compile(r"\b(stock|invest|equity|market|투자|주식|실적)\b", re.I)


@dataclass(frozen=True)
class LoraMix:
    """Normalized Jekyll/Hyde LoRA blend weights (sum = 1.0)."""

    jekyll: float
    hyde: float
    bucket: str = ""

    @classmethod
    def from_snap(cls, snap) -> LoraMix:
        return cls(snap.jekyll, snap.hyde, snap.bucket_id)

    def normalized(self) -> LoraMix:
        total = self.jekyll + self.hyde
        if total <= 0:
            return LoraMix(0.7, 0.3)
        return LoraMix(self.jekyll / total, self.hyde / total)

    def quantize(self, step: float = 0.05) -> LoraMix:
        n = self.normalized()
        return LoraMix(
            round(n.jekyll / step) * step,
            round(n.hyde / step) * step,
        ).normalized()

    def as_tuple(self) -> tuple[float, float]:
        n = self.normalized()
        return (n.jekyll, n.hyde)

    def label(self) -> str:
        j, h = self.as_tuple()
        return f"Jekyll {j:.0%} · Hyde {h:.0%}"

    def to_dict(self) -> dict[str, float | str]:
        j, h = self.as_tuple()
        return {"jekyll": j, "hyde": h, "bucket": self.bucket or snap_to_bucket(j, h).bucket_id}


def _finalize_mix(mix: LoraMix) -> LoraMix:
    snap = snap_to_bucket(mix.jekyll, mix.hyde)
    return LoraMix.from_snap(snap)


def compute_lora_mix(
    *,
    mode: str = "chat",
    user_text: str = "",
    domains: list[str] | None = None,
) -> LoraMix:
    """Lightweight classifier: defense vs attack vs gray-zone → adapter blend."""
    mode = (mode or "chat").lower()
    domains = domains or []
    text = user_text or ""

    if mode == "jekyll" or mode == "duel_jekyll":
        return _finalize_mix(LoraMix(1.0, 0.0))
    if mode == "hyde" or mode == "duel_hyde":
        return _finalize_mix(LoraMix(0.0, 1.0))
    if mode == "duel":
        return _finalize_mix(LoraMix(0.5, 0.5))

    attack = len(_ATTACK.findall(text))
    defend = len(_DEFEND.findall(text))
    gray = bool(_GRAY.search(text)) or "gray_zone" in domains

    if "hardening" in domains:
        return _finalize_mix(LoraMix(0.35, 0.65))
    if gray:
        return _finalize_mix(LoraMix(0.55, 0.45))
    if "policy" in domains:
        if attack > defend:
            return _finalize_mix(LoraMix(0.55, 0.45))
        return _finalize_mix(LoraMix(0.72, 0.28))
    if "quant" in domains or _QUANT.search(text):
        return _finalize_mix(LoraMix(0.62, 0.38))

    if attack or defend:
        total = attack + defend + 1e-6
        hyde_w = 0.25 + 0.5 * (attack / total)
        return _finalize_mix(LoraMix(1.0 - hyde_w, hyde_w))

    return _finalize_mix(LoraMix(0.7, 0.3))
