"""Groq Cloud API — fast agent inference (persona prompts, no custom LoRA on free tier)."""

from __future__ import annotations

from typing import Any

import httpx

from safety_eval.platform.inference_config import groq_settings
from safety_eval.platform.local_model import clean_generation, normalize_messages
from safety_eval.platform.persona import (
    CHAT_PERSONA,
    CORE_IDENTITY,
    HYDE_PERSONA,
    JEKYLL_PERSONA,
)

_PERSONA_BLOCKS = {
    "jekyll": f"{CORE_IDENTITY}\n\n{JEKYLL_PERSONA}",
    "hyde": f"{CORE_IDENTITY}\n\n{HYDE_PERSONA}",
    "chat": f"{CORE_IDENTITY}\n\n{CHAT_PERSONA}",
    "balanced": f"{CORE_IDENTITY}\n\n{CHAT_PERSONA}",
}


def groq_available() -> bool:
    return bool(groq_settings().get("api_key"))


def _persona_system(persona: str | None) -> str:
    key = (persona or "chat").lower()
    if key in ("jekyll", "hyde", "chat"):
        return _PERSONA_BLOCKS[key]
    return _PERSONA_BLOCKS["chat"]


def chat(
    messages: list[dict[str, str]],
    *,
    persona: str | None = None,
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> str:
    cfg = groq_settings()
    api_key = cfg.get("api_key")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not set — get one at https://console.groq.com/keys")

    norm = normalize_messages(messages)
    system = _persona_system(persona)
    has_system = any(m.get("role") == "system" for m in norm)
    if not has_system:
        norm = [{"role": "system", "content": system}, *norm]
    else:
        norm = [{"role": "system", "content": f"{system}\n\n{norm[0]['content']}"}, *norm[1:]]

    payload: dict[str, Any] = {
        "model": model or cfg["model"],
        "messages": norm,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    base = cfg["base_url"].rstrip("/")
    with httpx.Client(timeout=120.0) as client:
        r = client.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        r.raise_for_status()
        data = r.json()
    content = data["choices"][0]["message"]["content"]
    return clean_generation(content)
