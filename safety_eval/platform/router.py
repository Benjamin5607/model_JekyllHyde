"""Lightweight persona routing — slim prompts per mode (2B-friendly)."""

from __future__ import annotations

from typing import Literal

PersonaFocus = Literal["jekyll", "hyde", "balanced"]


def resolve_persona_focus(
    *,
    mode: str,
    user_text: str = "",
    domains: list[str] | None = None,
) -> PersonaFocus:
    mode = (mode or "chat").lower()
    domains = domains or []
    if mode == "jekyll":
        return "jekyll"
    if mode == "hyde":
        return "hyde"
    if mode.startswith("duel_jekyll"):
        return "jekyll"
    if mode.startswith("duel_hyde"):
        return "hyde"
    if "hardening" in domains or "gray_zone" in domains:
        return "hyde" if mode == "hyde" else "balanced"
    if "policy" in domains:
        return "jekyll"
    if "quant" in domains:
        return "balanced"
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
