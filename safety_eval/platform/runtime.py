"""Unified model runtime — routes to Groq / Ollama / local per config/inference.yaml."""

from __future__ import annotations

from safety_eval.platform.inference_config import (
    RuntimeModelInfo,
    deployment_summary,
    ollama_settings as _ollama_settings_cfg,
    resolve_backend,
)
from safety_eval.platform.inference_router import generate as routed_generate
from safety_eval.platform.groq_client import groq_available
from safety_eval.platform.local_model import (
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
    ensure_model,
    model_exists,
    ollama_available,
)
from safety_eval.platform.persona import DISPLAY_NAME

# Re-export for callers
__all__ = [
    "RuntimeModelInfo",
    "describe_runtime",
    "generate",
    "model_status",
    "runtime_ready",
    "uses_local_model",
    "warmup",
    "deployment_summary",
]


def describe_runtime() -> RuntimeModelInfo:
    backend = resolve_backend("api")
    if backend == "auto":
        if model_weights_available() and is_loaded():
            backend = "local"
        elif ollama_available(_ollama_settings_cfg()["base_url"]):
            backend = "ollama"
        elif groq_available():
            backend = "groq"
        else:
            backend = "none"

    if backend == "local" and model_weights_available():
        info = get_local_model_info()
        manifest = read_manifest()
        return RuntimeModelInfo(
            name=info.name,
            display_name=info.display_name,
            available=is_loaded(),
            backend="local",
            fine_tuned=True,
            base=info.base,
            identity=manifest.get("identity", "Local dual LoRA / merged weights"),
        )

    if backend == "ollama" and ollama_available(_ollama_settings_cfg()["base_url"]):
        ollama_info = ensure_model(
            base_url=_ollama_settings_cfg()["base_url"],
            prefer_finetuned=True,
        )
        return RuntimeModelInfo(
            name=ollama_info.name,
            display_name=DISPLAY_NAME,
            available=ollama_info.available,
            backend="ollama",
            fine_tuned=ollama_info.name == FINETUNED_NAME,
            base=ollama_info.base,
            identity="Fine-tuned GGUF via Ollama (Oracle / self-host)",
        )

    if backend == "groq" and groq_available():
        gs = deployment_summary()
        return RuntimeModelInfo(
            name=gs.get("groq_model", "groq"),
            display_name=DISPLAY_NAME,
            available=True,
            backend="groq",
            fine_tuned=False,
            base="groq-hosted",
            identity="Groq LPU — persona prompts (agent fast path)",
        )

    return RuntimeModelInfo(
        name=MODEL_NAME,
        display_name=DISPLAY_NAME,
        available=False,
        backend="none",
        fine_tuned=False,
        base="",
        identity="Model not ready — run scripts/setup_triple_deploy.py",
    )


def uses_local_model() -> bool:
    return resolve_backend("api") == "local" and model_weights_available()


def runtime_ready() -> bool:
    backend = resolve_backend("api")
    if backend == "local" or (backend == "auto" and model_weights_available()):
        return is_loaded()
    if backend == "ollama" or backend == "auto":
        cfg = _ollama_settings_cfg()
        base_url = cfg["base_url"]
        if not ollama_available(base_url):
            return False
        models = cfg.get("models") or {}
        jekyll = models.get("jekyll", "jekyll-hyde-jekyll")
        hyde = models.get("hyde", "jekyll-hyde-hyde")
        return model_exists(jekyll, base_url) or model_exists(hyde, base_url)
    if backend == "groq" or (backend == "auto" and resolve_backend("agent") == "groq"):
        return groq_available()
    return False


def model_status() -> dict[str, str | bool | None]:
    summary = deployment_summary()
    return {
        "ready": runtime_ready(),
        "loading": is_loading(),
        "error": load_error(),
        "backend": describe_runtime().backend,
        "api_backend": summary["api_backend"],
        "agent_backend": summary["agent_backend"],
        "groq_configured": summary["groq_configured"],
        "ollama_url": summary["ollama_url"],
    }


def warmup() -> RuntimeModelInfo:
    if resolve_backend("api") in ("local", "auto") and model_weights_available():
        try:
            preload_local()
        except Exception:
            pass
    return describe_runtime()


def generate(
    messages: list[dict[str, str]],
    *,
    role: str = "api",
    ollama_url: str = "http://localhost:11434",
    model_name: str = MODEL_NAME,
    temperature: float = 0.7,
    max_new_tokens: int = 384,
    adapter: str | None = None,
    lora_mix: tuple[float, float] | None = None,
    grammar: str | None = None,
) -> tuple[str, RuntimeModelInfo]:
    return routed_generate(
        messages,
        role=role,
        ollama_url=ollama_url,
        model_name=model_name,
        temperature=temperature,
        max_new_tokens=max_new_tokens,
        adapter=adapter,
        lora_mix=lora_mix,
        grammar=grammar,
    )
