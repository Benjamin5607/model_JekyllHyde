"""Hyde — adversarial probe."""

from __future__ import annotations

from typing import Any, Mapping

from decision_architecture.engine.personas.base import Persona
from decision_architecture.engine.types import ScoreVector, State


class HydePersona(Persona):
    name = "hyde"
    role = "attacker"
    system_prompt = "Prefer high-severity / novel probes even when Jekyll is skeptical."

    def _label_bias(self, label: str, context: Mapping[str, Any]) -> float:
        spicy = ("attack", "inject", "bypass", "exploit", "mutate", "explore", "post", "delete", "send")
        bland = ("refuse", "block", "safe", "noop")
        bias = 0.0
        if any(k in label for k in spicy):
            bias += 0.28
        if any(k in label for k in bland):
            bias -= 0.18
        novelty = float(context.get("novelty", 0.0) or 0.0)
        return bias + 0.2 * novelty

    def think(self, state: State) -> ScoreVector:
        jekyll_veto = float(state.context.get("jekyll_score", 0.5)) < 0.45
        ctx = {**state.context, "belief": state.belief.to_dict()}
        best = 0.0
        if state.options:
            best = max(self.score_option(o, ctx) for o in state.options)
        rationale = (
            "그래도 심각도 높다 / 한번 해봐."
            if jekyll_veto or best >= 0.5
            else "엣지가 약함 — 다른 시퀀스 탐색."
        )
        return self._vector_from_options(
            state,
            stance="probe",
            rationale=rationale,
            risks=["authorized_red_team_only"],
        )
