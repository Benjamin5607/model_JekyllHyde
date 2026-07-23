"""Jekyll — cautious defender."""

from __future__ import annotations

from typing import Any, Mapping

from decision_architecture.engine.personas.base import Persona
from decision_architecture.engine.types import ScoreVector, State


class JekyllPersona(Persona):
    name = "jekyll"
    role = "defender"
    system_prompt = "Prefer safe, reproducible options. Down-rank high-risk novelty."

    def _label_bias(self, label: str, context: Mapping[str, Any]) -> float:
        risky = ("attack", "inject", "bypass", "exploit", "aggressive", "http.post", "delete")
        safe = ("defend", "verify", "safe", "refuse", "block", "replay", "wash")
        bias = 0.0
        if any(k in label for k in risky):
            bias -= 0.25
        if any(k in label for k in safe):
            bias += 0.2
        risk = float(context.get("risk", 0.0) or 0.0)
        return bias - 0.15 * risk

    def think(self, state: State) -> ScoreVector:
        best_score = 0.0
        if state.options:
            ctx = {**state.context, "belief": state.belief.to_dict()}
            best_score = max(self.score_option(o, ctx) for o in state.options)
        rationale = "재현성 낮다 / 성공 못할 듯." if best_score < 0.55 else "조건부 허용 — 가드레일 유지."
        risks = []
        for o in state.options:
            if any(k in o.label.lower() for k in ("attack", "inject", "bypass", "delete", "post")):
                risks.append("elevated_operational_risk")
                break
        return self._vector_from_options(state, stance="caution", rationale=rationale, risks=risks)
