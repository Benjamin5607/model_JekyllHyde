"""Dedicated MCP Guidelines Chat Platform."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime

from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from safety_eval.i18n.apac import APAC_LANGUAGES
from safety_eval.platform.engine import JekyllHydeEngine, Mode
from safety_eval.platform.model_registry import list_bases
from safety_eval.platform.ollama_client import MODEL_NAME, ensure_model, ollama_available
from safety_eval.platform.runtime import describe_runtime, runtime_ready, warmup
from safety_eval.store import get_guidelines_store

STATIC = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Jekyll & Hyde Guidelines Chat", version="1.0.0")
engine = JekyllHydeEngine()


class ChatRequest(BaseModel):
    message: str
    mode: Mode = "chat"


class GuidelinesRequest(BaseModel):
    text: str
    title: str = "Community Guidelines"


class AppendRequest(BaseModel):
    section: str
    text: str


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/status")
def status() -> dict:
    store = get_guidelines_store()
    snap = store.snapshot()
    runtime = describe_runtime()
    ollama_up = ollama_available(engine.config.ollama_url)
    return {
        "app": "guidelines-chat",
        "mcp_sync": True,
        "guidelines_title": snap.title,
        "guidelines_source": snap.source,
        "guidelines_updated_at": snap.updated_at,
        "guidelines_chars": len(snap.text),
        "model": runtime.name,
        "display_name": runtime.display_name,
        "fine_tuned": runtime.fine_tuned,
        "backend": runtime.backend,
        "base": runtime.base,
        "model_ready": runtime_ready(),
        "ollama_running": ollama_up,
        "apac_languages": list(APAC_LANGUAGES.keys()),
        "server_time": datetime.now(UTC).isoformat(),
    }


@app.get("/api/guidelines")
def get_guidelines() -> dict:
    s = get_guidelines_store().snapshot()
    return {"title": s.title, "text": s.text, "source": s.source, "updated_at": s.updated_at}


@app.post("/api/guidelines")
def set_guidelines(body: GuidelinesRequest) -> dict:
    s = get_guidelines_store().set_text(body.text, title=body.title, source="guidelines-chat")
    return {"ok": True, "updated_at": s.updated_at, "chars": len(s.text)}


@app.post("/api/guidelines/append")
def append_guidelines(body: AppendRequest) -> dict:
    store = get_guidelines_store()
    merged = store.text.rstrip() + f"\n\n## {body.section.strip()}\n{body.text.strip()}\n"
    s = store.set_text(merged, title=store.title, source="guidelines-chat-append")
    return {"ok": True, "updated_at": s.updated_at}


@app.get("/api/bases")
def bases() -> dict:
    return {"bases": list_bases()}


@app.post("/api/models/ensure")
def models_ensure(base: str = "gemma2-2b") -> dict:
    if runtime_ready():
        info = warmup()
        return {
            "ok": True,
            "model": info.name,
            "base": info.base,
            "backend": info.backend,
            "fine_tuned": info.fine_tuned,
        }
    if not ollama_available(engine.config.ollama_url):
        raise HTTPException(503, "Train LoRA or start Ollama")
    info = ensure_model(base_key=base, base_url=engine.config.ollama_url)
    engine.config.model = info.name
    return {"ok": info.available, "model": info.name, "base": info.base, "backend": "ollama"}


@app.post("/api/chat")
def chat(body: ChatRequest) -> dict:
    resp = engine.complete(body.message, mode=body.mode)
    snap = get_guidelines_store().snapshot()
    runtime = describe_runtime()
    return {
        "content": resp.content,
        "mode": resp.mode,
        "model": runtime.name,
        "backend": runtime.backend,
        "fine_tuned": runtime.fine_tuned,
        "language": resp.language,
        "jekyll_verdict": resp.jekyll_verdict,
        "blocked_input": resp.blocked_input,
        "guidelines_updated_at": snap.updated_at,
        "meta": resp.meta,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="MCP Guidelines Chat Platform")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8770)
    args = parser.parse_args()
    uvicorn.run("safety_eval.apps.guidelines_chat.server:app", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
