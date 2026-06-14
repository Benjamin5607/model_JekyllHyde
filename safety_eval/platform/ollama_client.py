"""Ollama integration — create and run the jekyll-hyde model."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from safety_eval.platform.model_registry import get_base, list_bases
from safety_eval.platform.persona import MODEL_NAME

MODELS_DIR = Path(__file__).resolve().parent.parent.parent / "models"
MODELFILE = MODELS_DIR / "Modelfile"
FINETUNED_NAME = "jekyll-hyde-ft"


@dataclass
class OllamaModelInfo:
    name: str
    available: bool
    base: str = ""
    size: str = ""


def default_base_key() -> str:
    return "gemma2-2b"


def ollama_available(base_url: str = "http://localhost:11434") -> bool:
    try:
        with httpx.Client(timeout=3.0) as client:
            r = client.get(f"{base_url.rstrip('/')}/api/tags")
            return r.status_code == 200
    except Exception:
        return False


def list_models(base_url: str = "http://localhost:11434") -> list[dict[str, Any]]:
    with httpx.Client(timeout=30.0) as client:
        r = client.get(f"{base_url.rstrip('/')}/api/tags")
        r.raise_for_status()
        return r.json().get("models", [])


def model_exists(name: str, base_url: str = "http://localhost:11434") -> bool:
    models = list_models(base_url)
    return any(m.get("name", "").startswith(name) for m in models)


def pull_base(base_key: str | None = None, base_url: str = "http://localhost:11434") -> str:
    spec = get_base(base_key)
    with httpx.Client(timeout=600.0) as client:
        r = client.post(
            f"{base_url.rstrip('/')}/api/pull",
            json={"name": spec.ollama, "stream": False},
        )
        r.raise_for_status()
    return f"Pulled base model: {spec.ollama}"


def create_jekyll_hyde_model(
    base_key: str | None = None,
    *,
    modelfile: Path | None = None,
    model_name: str = MODEL_NAME,
) -> str:
    spec = get_base(base_key)
    modelfile = modelfile or MODELFILE
    if not modelfile.exists():
        raise FileNotFoundError(f"Modelfile not found: {modelfile}")

    content = modelfile.read_text(encoding="utf-8")
    content = content.replace("{{BASE}}", spec.ollama)
    temp = modelfile.parent / "Modelfile.generated"
    temp.write_text(content, encoding="utf-8")

    result = subprocess.run(
        ["ollama", "create", model_name, "-f", str(temp)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or "ollama create failed")
    return f"Created model '{model_name}' from base '{spec.ollama}' ({spec.key})"


def chat(
    messages: list[dict[str, str]],
    *,
    model: str = MODEL_NAME,
    base_url: str = "http://localhost:11434",
    temperature: float = 0.7,
) -> str:
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature},
    }
    with httpx.Client(timeout=300.0) as client:
        r = client.post(f"{base_url.rstrip('/')}/api/chat", json=payload)
        r.raise_for_status()
        data = r.json()
    return data.get("message", {}).get("content", "")


def ensure_model(
    base_url: str = "http://localhost:11434",
    base_key: str | None = None,
    model_name: str = MODEL_NAME,
    prefer_finetuned: bool = True,
) -> OllamaModelInfo:
    if not ollama_available(base_url):
        return OllamaModelInfo(name=model_name, available=False)

    if prefer_finetuned and model_exists(FINETUNED_NAME, base_url):
        spec = get_base(base_key)
        return OllamaModelInfo(name=FINETUNED_NAME, available=True, base=f"{spec.key} (LoRA)")

    spec = get_base(base_key)
    if not model_exists(spec.ollama, base_url):
        pull_base(spec.key, base_url)

    if not model_exists(model_name, base_url):
        create_jekyll_hyde_model(base_key=spec.key, model_name=model_name)

    return OllamaModelInfo(name=model_name, available=True, base=spec.ollama)


def available_bases() -> list[dict]:
    return list_bases()
