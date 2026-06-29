"""Lightweight persona routing — slim prompts per mode (2B-friendly)."""

from __future__ import annotations

from typing import Literal

from safety_eval.platform.lora_router import LoraMix, compute_lora_mix

PersonaFocus = Literal["jekyll", "hyde", "balanced"]


def resolve_persona_focus(
    *,
    mode: str,
    user_text: str = "",
    domains: list[str] | None = None,
) -> PersonaFocus:
    mix = compute_lora_mix(mode=mode, user_text=user_text, domains=domains)
    j, h = mix.as_tuple()
    if j >= 0.85:
        return "jekyll"
    if h >= 0.85:
        return "hyde"
    return "balanced"


def slim_core_identity(focus: PersonaFocus) -> str:
    if focus == "jekyll":
        return (
            "You are JEKYLL — independent Gemma-derived model. NOT Gemma/ChatGPT. "
            "Defend guidelines, refuse harm, structured policy/market analysis. "
            "Reply in the user's language."
        )
    if focus == "hyde":
        return (
            "You are HYDE — authorized red-team facet. NOT Gemma/ChatGPT. "
            "Probe policy edges and gaps; no operational harm. "
            "Reply in the user's language."
        )
    return (
        "You are Jekyll & Hyde — independent dual-nature model. NOT Gemma/ChatGPT. "
        "Jekyll defends; Hyde stress-tests. Reply in the user's language."
    )


__all__ = ["PersonaFocus", "LoraMix", "compute_lora_mix", "resolve_persona_focus", "slim_core_identity"]
