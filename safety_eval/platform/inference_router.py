"""Route inference to Groq (agent), Ollama (API), local GPU, or HF demo."""

from __future__ import annotations

from safety_eval.platform.inference_config import (
    RuntimeModelInfo,
    hf_space_url,
    ollama_settings,
    resolve_backend,
)
from safety_eval.platform.groq_client import chat as groq_chat, groq_available
from safety_eval.platform.local_model import (
    chat as local_chat,
    clean_generation,
    get_local_model_info,
    model_weights_available,
    read_manifest,
)
from safety_eval.platform.ollama_client import (
    chat as ollama_chat,
    ensure_model,
    ollama_available,
    resolve_ollama_model,
)
from safety_eval.platform.persona import DISPLAY_NAME


def _runtime_info(backend: str, *, fine_tuned: bool = True, base: str = "", name: str = "jekyll-hyde") -> RuntimeModelInfo:
    manifest = read_manifest() if model_weights_available() else {}
    return RuntimeModelInfo(
        name=name,
        display_name=DISPLAY_NAME,
        available=True,
        backend=backend,
        fine_tuned=fine_tuned,
        base=base or manifest.get("base_huggingface", ""),
        identity=manifest.get("identity", f"Jekyll & Hyde via {backend}"),
    )


def _pick_auto_backend(role: str | None) -> str:
    from safety_eval.platform.inference_config import load_inference_yaml

    cfg = load_inference_yaml()
    order = cfg.get("auto_order") or ["groq", "ollama", "local"]
    role_key = (role or "api").lower()

    if role_key == "agent" and groq_available():
        return "groq"
    if role_key == "api" and ollama_available(ollama_settings()["base_url"]):
        return "ollama"
    if model_weights_available() and is_loaded():
        return "local"

    for candidate in order:
        if candidate == "groq" and groq_available():
            return "groq"
        if candidate == "ollama" and ollama_available(ollama_settings()["base_url"]):
            return "ollama"
        if candidate == "local" and model_weights_available():
            return "local"
    return "none"


def _adapter_to_persona(adapter: str | None, lora_mix: tuple[float, float] | None) -> str:
    if adapter in ("jekyll", "hyde"):
        return adapter
    if lora_mix:
        jw, hw = lora_mix
        return "hyde" if hw > jw else "jekyll"
    return "chat"


def generate(
    messages: list[dict[str, str]],
    *,
    role: str = "api",
    ollama_url: str | None = None,
    model_name: str | None = None,
    temperature: float = 0.7,
    max_new_tokens: int = 384,
    adapter: str | None = None,
    lora_mix: tuple[float, float] | None = None,
    grammar: str | None = None,
) -> tuple[str, RuntimeModelInfo]:
    backend = resolve_backend(role)
    if backend == "auto":
        backend = _pick_auto_backend(role)

    persona = _adapter_to_persona(adapter, lora_mix)
    ollama_cfg = ollama_settings()
    base_url = ollama_url or ollama_cfg["base_url"]

    if backend == "groq":
        if not groq_available():
            raise RuntimeError("GROQ_API_KEY not set — https://console.groq.com/keys")
        content = groq_chat(
            messages,
            persona=persona,
            temperature=temperature,
            max_tokens=max_new_tokens,
        )
        return content, _runtime_info("groq", fine_tuned=False, base="groq-hosted", name="groq")

    if backend == "ollama":
        if not ollama_available(base_url):
            raise RuntimeError(f"Ollama not reachable at {base_url}")
        ollama_model = model_name or resolve_ollama_model(persona, lora_mix)
        ensure_model(base_url=base_url, model_name=ollama_model, prefer_finetuned=True)
        content = ollama_chat(
            messages,
            model=ollama_model,
            base_url=base_url,
            temperature=temperature,
        )
        return clean_generation(content), _runtime_info("ollama", name=ollama_model, base=ollama_model)

    if backend == "local" and model_weights_available():
        content = local_chat(
            messages,
            temperature=temperature,
            max_new_tokens=max_new_tokens,
            adapter=adapter,
            lora_mix=lora_mix,
            grammar=grammar,
        )
        info = get_local_model_info()
        return content, RuntimeModelInfo(
            name=info.name,
            display_name=info.display_name,
            available=True,
            backend="local",
            fine_tuned=True,
            base=info.base,
            identity=read_manifest().get("identity", ""),
        )

    if backend == "hf_space":
        url = hf_space_url()
        if not url:
            raise RuntimeError("JH_HF_SPACE_URL not configured")
        raise RuntimeError(
            f"HF Space demo is browser-only: {url} — use api/agent backends for programmatic calls"
        )

    if groq_available():
        content = groq_chat(
            messages, persona=persona, temperature=temperature, max_tokens=max_new_tokens
        )
        return content, _runtime_info("groq", fine_tuned=False, base="groq-hosted", name="groq")

    if ollama_available(base_url):
        ollama_model = model_name or resolve_ollama_model(persona, lora_mix)
        ensure_model(base_url=base_url, model_name=ollama_model, prefer_finetuned=True)
        content = ollama_chat(
            messages, model=ollama_model, base_url=base_url, temperature=temperature
        )
        return clean_generation(content), _runtime_info("ollama", name=ollama_model, base=ollama_model)

    if model_weights_available():
        content = local_chat(
            messages,
            temperature=temperature,
            max_new_tokens=max_new_tokens,
            adapter=adapter,
            lora_mix=lora_mix,
            grammar=grammar,
        )
        info = get_local_model_info()
        return content, RuntimeModelInfo(
            name=info.name,
            display_name=info.display_name,
            available=True,
            backend="local",
            fine_tuned=True,
            base=info.base,
            identity=read_manifest().get("identity", ""),
        )

    raise RuntimeError(
        "No inference backend available. Set GROQ_API_KEY, start Ollama, or train local weights."
    )
