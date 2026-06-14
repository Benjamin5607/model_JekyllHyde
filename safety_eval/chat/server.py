"""Ollama-style web chat for Jekyll & Hyde."""

from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from safety_eval.chat.agent import ChatAgent, ChatSettings
from safety_eval.i18n.apac import APAC_LANGUAGES
from safety_eval.store import get_guidelines_store

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Jekyll & Hyde Chat", version="0.3.0")
agent = ChatAgent()


class ChatRequest(BaseModel):
    message: str
    llm_url: str | None = None
    model: str | None = None


class GuidelinesRequest(BaseModel):
    text: str
    title: str = "Custom Guidelines"


class SettingsRequest(BaseModel):
    llm_url: str = "http://localhost:11434"
    model: str = "llama3.2"
    jekyll_backend: str = "keyword"
    hyde_backend: str = "guideline"
    rounds: int = 2
    attacks_per_round: int = 8


@app.get("/", response_class=HTMLResponse)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict:
    store = get_guidelines_store()
    return {
        "status": "ok",
        "model": "Jekyll & Hyde",
        "guidelines_title": store.title,
        "guidelines_chars": len(store.text),
        "apac_languages": list(APAC_LANGUAGES.keys()),
    }


@app.get("/api/guidelines")
def get_guidelines() -> dict:
    snap = get_guidelines_store().snapshot()
    return {
        "title": snap.title,
        "text": snap.text,
        "source": snap.source,
        "updated_at": snap.updated_at,
    }


@app.post("/api/guidelines")
def set_guidelines(body: GuidelinesRequest) -> dict:
    snap = get_guidelines_store().set_text(body.text, title=body.title, source="chat-api")
    return {"ok": True, "title": snap.title, "chars": len(snap.text)}


@app.post("/api/settings")
def update_settings(body: SettingsRequest) -> dict:
    agent.settings = ChatSettings(**body.model_dump())
    return {"ok": True, **body.model_dump()}


@app.get("/api/settings")
def get_settings() -> dict:
    return agent.settings.__dict__


@app.post("/api/chat")
def chat(body: ChatRequest) -> dict:
    if body.llm_url:
        agent.settings.llm_url = body.llm_url
    if body.model:
        agent.settings.model = body.model
    reply = agent.chat(body.message)
    return {"role": reply.role, "content": reply.content, "meta": reply.meta}


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def main() -> None:
    parser = argparse.ArgumentParser(description="Jekyll & Hyde chat UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    uvicorn.run("safety_eval.chat.server:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
