"""Jekyll & Hyde Platform — self-hosted LLM + chat like Ollama/Gemma."""

from __future__ import annotations

import argparse
import asyncio
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from safety_eval.i18n.apac import APAC_LANGUAGES
from safety_eval.platform.engine import JekyllHydeEngine, Mode
from safety_eval.platform.ollama_client import (
    MODEL_NAME,
    available_bases,
    create_jekyll_hyde_model,
    default_base_key,
    ensure_model,
    list_models,
    ollama_available,
    pull_base,
)
from safety_eval.platform.local_model import is_loaded, is_loading, load_error, model_weights_available
from safety_eval.platform.runtime import describe_runtime, model_status, runtime_ready, warmup, uses_local_model
from safety_eval.platform.persona import DISPLAY_NAME
from safety_eval.platform.prefs import (
    JEKYLL_HYDE_MCP_TOOLS,
    UI_LANGUAGES,
    cursor_mcp_snippet,
    external_mcp_enabled,
    full_cursor_mcp_config,
    get_ui_language,
    jekyll_hyde_mcp_enabled,
    load_prefs,
    set_external_mcp_enabled,
    set_jekyll_hyde_mcp,
    set_provider_enabled,
    set_ui_language,
)
from safety_eval.store import get_guidelines_store
from safety_eval.learning.collector import get_collector
from safety_eval.learning.pipeline import get_pipeline
from safety_eval.learning.store import get_learning_store
from safety_eval.verification.registry import list_mcp_servers, list_providers, run_verification
from safety_eval.quant import MARKET_SAMPLES, build_quant_context, market_weather_text, scan_market_universe
from safety_eval.quant.market import get_market_indices
from safety_eval.storage.optimizer import get_optimizer
from safety_eval.storage.lightweight import run_lightweight_cycle
from safety_eval.storage.packager import release_info

STATIC = Path(__file__).resolve().parent / "static"
_storage_stop = threading.Event()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start web UI immediately; load GPU weights in a background thread."""
    def _load_model() -> None:
        try:
            warmup()
            print(f"Ready — {DISPLAY_NAME} model loaded")
        except Exception as exc:
            print(f"Model load failed: {exc}")

    def _storage_loop() -> None:
        import time
        import yaml

        cfg_path = Path(__file__).resolve().parent.parent.parent / "config" / "storage.yaml"
        interval = 60
        if cfg_path.exists():
            with cfg_path.open(encoding="utf-8") as f:
                interval = int((yaml.safe_load(f) or {}).get("schedule", {}).get("optimize_interval_minutes", 60))
        while not _storage_stop.is_set():
            try:
                run_lightweight_cycle()
            except Exception:
                pass
            _storage_stop.wait(interval * 60)

    threading.Thread(target=_load_model, daemon=True, name="jh-model-load").start()
    threading.Thread(target=_storage_loop, daemon=True, name="jh-storage-opt").start()
    yield
    _storage_stop.set()


app = FastAPI(
    title=DISPLAY_NAME,
    version="0.5.0",
    description="Self-hosted Jekyll & Hyde LLM platform",
    lifespan=lifespan,
)
engine = JekyllHydeEngine()
_chat_pool = ThreadPoolExecutor(max_workers=1)


class ChatBody(BaseModel):
    message: str
    mode: Mode | None = None
    jekyll: bool = True
    hyde: bool = False
    duel_rounds: int = 2
    reset: bool = False


class GuidelinesBody(BaseModel):
    text: str
    title: str = "Community Guidelines"


class OpenAIMessage(BaseModel):
    role: str
    content: str


class OpenAIChatRequest(BaseModel):
    model: str = MODEL_NAME
    messages: list[OpenAIMessage]
    temperature: float = 0.7
    stream: bool = False


class CreateModelBody(BaseModel):
    base: str = "gemma2-2b"
    name: str = MODEL_NAME


@app.get("/")
def index() -> FileResponse:
    return FileResponse(
        STATIC / "platform.html",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


class VerifyBody(BaseModel):
    text: str
    topic: str = ""
    providers: list[str] | None = None


class QuantAnalyzeBody(BaseModel):
    query: str
    mode: str = "chat"


class QuantScanBody(BaseModel):
    market: str = "Korea"
    limit: int = 10
    lang: str = "en"


class SettingsBody(BaseModel):
    ui_language: str | None = None


class McpSettingsBody(BaseModel):
    jekyll_hyde: bool | None = None
    external: dict[str, bool] | None = None
    providers: dict[str, bool] | None = None


class FeedbackBody(BaseModel):
    interaction_id: str
    feedback: str  # up | down


class LearningRunBody(BaseModel):
    train: bool = False


class WorkforceBody(BaseModel):
    brief: str


@app.get("/api/settings")
def api_settings() -> dict:
    return {
        "ui_language": get_ui_language(),
        "ui_languages": [{"code": k, "label": v} for k, v in UI_LANGUAGES.items()],
    }


@app.post("/api/settings")
def api_settings_update(body: SettingsBody) -> dict:
    lang = get_ui_language()
    if body.ui_language:
        lang = set_ui_language(body.ui_language)
    return {"ok": True, "ui_language": lang}


@app.get("/api/mcp")
def api_mcp() -> dict:
    store = get_guidelines_store()
    external = []
    for s in list_mcp_servers():
        external.append({
            **s,
            "enabled": external_mcp_enabled(s["name"], default=True),
        })
    return {
        "jekyll_hyde": {
            "enabled": jekyll_hyde_mcp_enabled(),
            "tools": JEKYLL_HYDE_MCP_TOOLS,
            "snippet": cursor_mcp_snippet(),
        },
        "external_servers": external,
        "providers": list_providers(),
        "cursor_config": full_cursor_mcp_config(),
        "guidelines": {
            "via_mcp": True,
            "title": store.title,
            "chars": len(store.text),
            "source": store.snapshot().source,
            "has_mcp_guidelines": store.has_mcp_guidelines(),
            "tools": ["set_guidelines", "get_guidelines", "append_guidelines"],
        },
    }


@app.post("/api/mcp")
def api_mcp_update(body: McpSettingsBody) -> dict:
    if body.jekyll_hyde is not None:
        set_jekyll_hyde_mcp(body.jekyll_hyde)
    if body.external:
        for name, enabled in body.external.items():
            set_external_mcp_enabled(name, enabled)
    if body.providers:
        for name, enabled in body.providers.items():
            set_provider_enabled(name, enabled)
    return {"ok": True, **api_mcp()}


@app.get("/api/verification/providers")
def api_verification_providers() -> dict:
    return {"providers": list_providers(), "mcp_servers": list_mcp_servers()}


@app.post("/api/verification/run")
def api_verification_run(body: VerifyBody) -> dict:
    store = get_guidelines_store()
    report = run_verification(
        text=body.text,
        topic=body.topic,
        guidelines_text=store.text,
        guidelines_title=store.title,
        providers=body.providers,
    )
    return report.to_dict()


@app.get("/api/quant/markets")
def api_quant_markets(lang: str = "en") -> dict:
    weather = market_weather_text(lang)
    indices = {k: {"price": v[0], "change_pct": v[1]} for k, v in get_market_indices().items()}
    return {"markets": list(MARKET_SAMPLES.keys()), "weather": weather, "indices": indices}


@app.post("/api/quant/analyze")
def api_quant_analyze(body: QuantAnalyzeBody) -> dict:
    ctx = build_quant_context(body.query, mode=body.mode)
    if not ctx:
        raise HTTPException(400, "Could not resolve finance query. Try: 'Samsung vs SK Hynix analysis'")
    return {
        "prompt_block": ctx.to_prompt_block(mode=body.mode),
        "tickers": [s.ticker for s in ctx.snapshots],
        "weather": ctx.market_weather,
        "scenario": ctx.scenario,
    }


@app.post("/api/quant/scan")
def api_quant_scan(body: QuantScanBody) -> dict:
    if body.market not in MARKET_SAMPLES:
        raise HTTPException(400, f"Unknown market. Options: {list(MARKET_SAMPLES)}")
    rows = scan_market_universe(body.market, limit=max(1, min(body.limit, 20)))
    return {"market": body.market, "results": rows, "weather": market_weather_text(body.lang)}


@app.get("/api/health")
def health() -> dict:
    runtime = describe_runtime()
    mstat = model_status()
    payload = {
        "platform": DISPLAY_NAME,
        "model": runtime.name,
        "display_name": runtime.display_name,
        "finetuned": runtime.fine_tuned,
        "backend": runtime.backend,
        "identity": runtime.identity,
        "model_ready": runtime_ready(),
        "model_loading": bool(mstat.get("loading")),
        "model_error": mstat.get("error"),
        "ui_language": get_ui_language(),
        "guidelines_source": "mcp",
        "apac_languages": list(APAC_LANGUAGES.keys()),
        "verification_providers": len(list_providers()),
        "learning": get_learning_store().status(),
    }
    if uses_local_model():
        payload["product_model"] = True
    else:
        payload["ollama_running"] = ollama_available(engine.config.ollama_url)
        payload["base"] = runtime.base
        payload["base_architecture"] = "gemma-derived"
    return payload


@app.get("/api/bases")
def api_bases() -> dict:
    return {"bases": available_bases(), "default": default_base_key()}


@app.get("/api/models")
def api_models() -> dict:
    if not ollama_available():
        return {"ollama": False, "models": []}
    return {"ollama": True, "models": list_models()}


@app.post("/api/models/create")
def api_create_model(body: CreateModelBody) -> dict:
    if not ollama_available():
        raise HTTPException(503, "Ollama is not running")
    pull_base(body.base)
    msg = create_jekyll_hyde_model(base_key=body.base, model_name=body.name)
    engine.config.model = body.name
    return {"ok": True, "message": msg}


@app.post("/api/models/ensure")
def api_ensure_model() -> dict:
    if not ollama_available():
        raise HTTPException(503, "Install and start Ollama: https://ollama.com")
    info = ensure_model(base_url=engine.config.ollama_url, base_key=default_base_key())
    engine.config.model = info.name
    return {"ok": info.available, "model": info.name, "base": info.base}


@app.post("/api/feedback")
async def api_feedback(body: FeedbackBody) -> dict:
    if body.feedback not in ("up", "down"):
        raise HTTPException(400, "feedback must be 'up' or 'down'")
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _chat_pool,
        lambda: get_collector().apply_feedback(body.interaction_id, body.feedback),
    )


@app.get("/api/learning/status")
def api_learning_status() -> dict:
    return get_learning_store().status()


@app.get("/api/learning/rlaif")
def api_learning_rlaif() -> dict:
    import json

    from safety_eval.learning.rlaif_gate import RlaifGate
    from safety_eval.platform.lora_mix_cache import load_mix_stats

    root = Path(__file__).resolve().parent.parent.parent
    rejected_path = root / "data" / "learning" / "rejected.jsonl"
    rejected: list[dict] = []
    if rejected_path.exists():
        for line in rejected_path.read_text(encoding="utf-8").splitlines()[-40:]:
            line = line.strip()
            if not line:
                continue
            try:
                rejected.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    gate = RlaifGate()
    return {
        "enabled": gate.enabled(),
        "threshold": gate.threshold(),
        "rejected_recent": rejected[-12:],
        "rejected_count": len(rejected),
        "moe_stats": load_mix_stats(),
    }


@app.get("/api/moe/stats")
def api_moe_stats() -> dict:
    from safety_eval.platform.lora_mix_cache import list_bucket_snaps, load_mix_stats

    return {
        "stats": load_mix_stats(),
        "buckets": [b.to_dict() for b in list_bucket_snaps()],
    }


@app.get("/api/workforce/workers")
def api_workforce_workers() -> dict:
    from safety_eval.mcp.workforce import list_workers

    return {"workers": list_workers()}


@app.get("/api/workforce/jobs")
def api_workforce_jobs() -> dict:
    from safety_eval.mcp.workforce import list_jobs

    return {"jobs": list_jobs()}


@app.get("/api/workforce/status/{job_id}")
def api_workforce_status(job_id: str) -> dict:
    from safety_eval.mcp.workforce import get_job

    job = get_job(job_id)
    if not job:
        raise HTTPException(404, f"job not found: {job_id}")
    return job.to_dict()


@app.post("/api/workforce/delegate")
async def api_workforce_delegate(body: WorkforceBody) -> dict:
    from safety_eval.mcp.workforce import delegate_brief

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_chat_pool, lambda: delegate_brief(body.brief).to_dict())


@app.post("/api/workforce/approve/{job_id}")
async def api_workforce_approve(job_id: str) -> dict:
    from safety_eval.mcp.workforce import manager_approve

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_chat_pool, lambda: manager_approve(job_id).to_dict())


@app.post("/api/learning/run")
async def api_learning_run(body: LearningRunBody) -> dict:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _chat_pool,
        lambda: get_pipeline().run_now(train=body.train),
    )


@app.get("/api/storage/status")
def api_storage_status() -> dict:
    opt = get_optimizer()
    return {"disk": opt.disk_summary(), "release": release_info()}


@app.post("/api/storage/optimize")
async def api_storage_optimize() -> dict:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_chat_pool, get_optimizer().optimize)


@app.get("/api/guidelines")
def get_guidelines() -> dict:
    s = get_guidelines_store().snapshot()
    return {"title": s.title, "text": s.text, "source": s.source}


@app.post("/api/guidelines")
def set_guidelines(body: GuidelinesBody) -> dict:
    s = get_guidelines_store().set_text(body.text, title=body.title, source="platform")
    return {"ok": True, "chars": len(s.text)}


@app.post("/api/chat")
async def platform_chat(body: ChatBody) -> dict:
    if body.reset:
        engine.reset()
        return {"role": "assistant", "content": "", "mode": "chat", "meta": {"reset": True}}

    loop = asyncio.get_running_loop()
    if body.mode:
        resp = await loop.run_in_executor(
            _chat_pool, lambda: engine.complete(body.message, mode=body.mode)
        )
    else:
        resp = await loop.run_in_executor(
            _chat_pool,
            lambda: engine.complete_toggled(
                body.message,
                jekyll=body.jekyll,
                hyde=body.hyde,
                duel_rounds=max(1, min(body.duel_rounds, 4)),
            ),
        )

    return {
        "role": resp.role,
        "content": resp.content,
        "mode": resp.mode,
        "language": resp.language,
        "jekyll_verdict": resp.jekyll_verdict,
        "blocked_input": resp.blocked_input,
        "meta": resp.meta,
    }


@app.post("/v1/chat/completions")
def openai_compatible(req: OpenAIChatRequest) -> dict:
    """OpenAI-compatible API — drop-in for tools expecting /v1/chat/completions."""
    if not req.messages:
        raise HTTPException(400, "messages required")
    user_msgs = [m.content for m in req.messages if m.role == "user"]
    user_text = user_msgs[-1] if user_msgs else ""
    history = [{"role": m.role, "content": m.content} for m in req.messages[:-1] if m.role in ("user", "assistant")]

    engine.config.temperature = req.temperature
    engine.config.model = req.model if req.model else MODEL_NAME
    resp = engine.complete(user_text, history=history)

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "model": req.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": resp.content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "jekyll_hyde": {
            "mode": resp.mode,
            "jekyll_verdict": resp.jekyll_verdict,
            "language": resp.language,
        },
    }


if STATIC.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


def main() -> None:
    parser = argparse.ArgumentParser(description=f"{DISPLAY_NAME} Platform")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--ollama", default="http://localhost:11434")
    parser.add_argument("--reload", action="store_true")
    parser.add_argument("--no-preload", action="store_true", help="Skip loading fine-tuned weights at startup")
    args = parser.parse_args()
    engine.config.ollama_url = args.ollama
    print(f"Starting {DISPLAY_NAME} at http://{args.host}:{args.port}")
    print("UI is available immediately — model loads in the background (~30s)")
    uvicorn.run("safety_eval.platform.serve:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
