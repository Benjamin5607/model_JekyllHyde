"""Unified model runtime — fine-tuned local weights first, Ollama fallback."""

from __future__ import annotations

from dataclasses import dataclass

from safety_eval.platform.local_model import (
    chat as local_chat,
    clean_generation,
    get_local_model_info,
    is_loaded,
    is_loading,
    load_error,
    model_weights_available,
    preload as preload_local,
    read_manifest,
)
from safety_eval.platform.ollama_client import (
    FINETUNED_NAME,
    MODEL_NAME,
    OllamaModelInfo,
    chat as ollama_chat,
    ensure_model,
    ollama_available,
)
from safety_eval.platform.persona import DISPLAY_NAME


@dataclass(frozen=True)
class RuntimeModelInfo:
    name: str
    display_name: str
    available: bool
    backend: str
    fine_tuned: bool
    base: str
    identity: str


def describe_runtime() -> RuntimeModelInfo:
    if model_weights_available():
        info = get_local_model_info()
        manifest = read_manifest()
        return RuntimeModelInfo(
            name=info.name,
            display_name=info.display_name,
            available=is_loaded(),
            backend="local",
            fine_tuned=True,
            base=info.base,
            identity=manifest.get(
                "identity",
                "Independent Gemma-derived model with merged LoRA weights",
            ),
        )

    if ollama_available():
        ollama_info = ensure_model(prefer_finetuned=True)
        if ollama_info.available and ollama_info.name == FINETUNED_NAME:
            return RuntimeModelInfo(
                name=ollama_info.name,
                display_name=DISPLAY_NAME,
                available=True,
                backend="ollama",
                fine_tuned=True,
                base=ollama_info.base,
                identity="Fine-tuned model served via Ollama",
            )
        if ollama_info.available:
            return RuntimeModelInfo(
                name=ollama_info.name,
                display_name=DISPLAY_NAME,
                available=True,
                backend="ollama",
                fine_tuned=False,
                base=ollama_info.base,
                identity="Prompt-tuned wrapper on base Gemma (run LoRA training for full model)",
            )

    return RuntimeModelInfo(
        name=MODEL_NAME,
        display_name=DISPLAY_NAME,
        available=False,
        backend="none",
        fine_tuned=False,
        base="",
        identity="Model not ready",
    )


def uses_local_model() -> bool:
    return model_weights_available()


def runtime_ready() -> bool:
    if model_weights_available():
        return is_loaded()
    if ollama_available():
        info = ensure_model(prefer_finetuned=True)
        return info.available
    return False


def model_status() -> dict[str, str | bool | None]:
    if model_weights_available():
        return {
            "ready": is_loaded(),
            "loading": is_loading(),
            "error": load_error(),
            "backend": "local",
        }
    ready = runtime_ready() if not is_loading() else False
    return {
        "ready": ready,
        "loading": False,
        "error": load_error(),
        "backend": "ollama" if ollama_available() else "none",
    }


def warmup() -> RuntimeModelInfo:
    if model_weights_available():
        try:
            preload_local()
        except Exception:
            pass
    return describe_runtime()


def generate(
    messages: list[dict[str, str]],
    *,
    ollama_url: str = "http://localhost:11434",
    model_name: str = MODEL_NAME,
    temperature: float = 0.7,
    max_new_tokens: int = 384,
    adapter: str | None = None,
) -> tuple[str, RuntimeModelInfo]:
    if model_weights_available():
        try:
            content = local_chat(
                messages,
                temperature=temperature,
                max_new_tokens=max_new_tokens,
                adapter=adapter,
            )
            return content, describe_runtime()
        except Exception:
            if not ollama_available(ollama_url):
                raise

    if not ollama_available(ollama_url):
        raise RuntimeError("Model not available. Train LoRA or start Ollama.")

    info = ensure_model(base_url=ollama_url, model_name=model_name, prefer_finetuned=True)
    content = ollama_chat(
        messages,
        model=info.name,
        base_url=ollama_url,
        temperature=temperature,
    )
    return clean_generation(content), describe_runtime()
