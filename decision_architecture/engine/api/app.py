"""Optional FastAPI surface for Security Lab / ZeroAI Workspace embedding."""

from __future__ import annotations

from typing import Any

from decision_architecture.engine.core import DecisionEngine, Option, State
from decision_architecture.engine.personas.registry import DOMAIN_PERSONAS, PersonaRegistry


def build_app():
    try:
        from fastapi import FastAPI
        from pydantic import BaseModel, Field
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Install decision-architecture[api] for HTTP surface") from exc

    app = FastAPI(title="Decision Architecture API", version="0.1.0")
    engine = DecisionEngine()
    registry = PersonaRegistry()

    class DecideRequest(BaseModel):
        domain: str = "security"
        options: list[dict[str, Any]]
        context: dict[str, Any] = Field(default_factory=dict)
        state: dict[str, Any] = Field(default_factory=dict)
        rounds: int = 1

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "engine": "decision-architecture"}

    @app.get("/personas")
    def personas() -> dict[str, Any]:
        return {"personas": registry.list(), "domains": DOMAIN_PERSONAS}

    @app.post("/decide")
    def decide(req: DecideRequest) -> dict[str, Any]:
        names = DOMAIN_PERSONAS.get(req.domain, ("jekyll", "hyde"))
        options = [
            Option(
                id=o["id"],
                label=o.get("label", o["id"]),
                payload=o.get("payload", {}),
                prior=float(o.get("prior", 0.0)),
            )
            for o in req.options
        ]
        state = State(data=dict(req.state))
        eng = DecisionEngine(personas=names, domain=req.domain)
        decision = eng.decide(options, context=req.context, state=state, rounds=req.rounds)
        return decision.to_dict()

    return app


def main() -> None:
    import uvicorn

    uvicorn.run(build_app(), host="127.0.0.1", port=8765)


if __name__ == "__main__":
    main()
