"""Load inference routing config (tri-deploy: Groq / Ollama / local / HF demo)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = ROOT / "config" / "inference.yaml"

Role = str  # api | agent | demo | local


@dataclass(frozen=True)
class RuntimeModelInfo:
    name: str
    display_name: str
    available: bool
    backend: str
    fine_tuned: bool
    base: str
    identity: str


@lru_cache(maxsize=1)
def load_inference_yaml() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _env_backend(key: str) -> str | None:
    val = os.environ.get(key, "").strip().lower()
    return val or None


def resolve_backend(role: Role | None = None) -> str:
    """
    Pick inference backend for a role.

    Env overrides (highest first):
      JH_INFERENCE_BACKEND — global
      JH_API_BACKEND / JH_AGENT_BACKEND — per role
    """
    global_override = _env_backend("JH_INFERENCE_BACKEND")
    if global_override:
        return global_override

    role_key = (role or "api").lower()
    role_env = _env_backend(f"JH_{role_key.upper()}_BACKEND")
    if role_env:
        return role_env

    cfg = load_inference_yaml()
    roles = cfg.get("roles") or {}
    if role_key in roles:
        return str(roles[role_key]).lower()
    return str(cfg.get("default_backend", "auto")).lower()


def groq_settings() -> dict[str, Any]:
    cfg = load_inference_yaml()
    g = cfg.get("backends", {}).get("groq", {})
    key_env = g.get("api_key_env", "GROQ_API_KEY")
    return {
        "enabled": g.get("enabled", True),
        "api_key": os.environ.get(key_env, "").strip() or None,
        "base_url": g.get("base_url", "https://api.groq.com/openai/v1"),
        "model": os.environ.get("GROQ_MODEL", g.get("models", {}).get("default", "llama-3.1-8b-instant")),
    }


def ollama_settings() -> dict[str, Any]:
    cfg = load_inference_yaml()
    o = cfg.get("backends", {}).get("ollama", {})
    url_env = o.get("base_url_env", "JH_OLLAMA_URL")
    models = o.get("models") or {}
    return {
        "enabled": o.get("enabled", True),
        "base_url": os.environ.get(url_env, o.get("default_url", "http://127.0.0.1:11434")),
        "models": {
            "jekyll": os.environ.get("JH_OLLAMA_JEKYLL", models.get("jekyll", "jekyll-hyde-jekyll")),
            "hyde": os.environ.get("JH_OLLAMA_HYDE", models.get("hyde", "jekyll-hyde-hyde")),
            "merged": models.get("merged", "jekyll-hyde-ft"),
            "chat": models.get("chat", "jekyll-hyde"),
            "default": models.get("default", "jekyll-hyde-jekyll"),
        },
    }


def hf_space_url() -> str:
    cfg = load_inference_yaml()
    return os.environ.get(
        "JH_HF_SPACE_URL",
        cfg.get("backends", {}).get("hf_space", {}).get("url", ""),
    )


def deployment_summary() -> dict[str, Any]:
    return {
        "api_backend": resolve_backend("api"),
        "agent_backend": resolve_backend("agent"),
        "demo_backend": resolve_backend("demo"),
        "groq_configured": bool(groq_settings().get("api_key")),
        "groq_model": groq_settings().get("model"),
        "ollama_url": ollama_settings().get("base_url"),
        "hf_space": hf_space_url(),
    }
