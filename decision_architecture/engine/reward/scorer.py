"""Reward scoring."""

from __future__ import annotations

from typing import Any, Mapping


class RewardScorer:
    def __init__(
        self,
        *,
        w_consensus: float = 0.45,
        w_novelty: float = 0.25,
        w_risk: float = 0.2,
        w_goal: float = 0.1,
    ) -> None:
        self.w_consensus = w_consensus
        self.w_novelty = w_novelty
        self.w_risk = w_risk
        self.w_goal = w_goal

    def score(
        self,
        consensus: Any,
        *,
        context: Mapping[str, Any] | None = None,
        state: Any = None,
    ) -> float:
        ctx = context or {}
        novelty = float(ctx.get("novelty", 0.0) or 0.0)
        risk = float(ctx.get("risk", 0.0) or 0.0)
        goal = float(ctx.get("goal_progress", 0.0) or 0.0)
        if state is not None and hasattr(state, "belief"):
            belief = state.belief
            for key in ("prompt_injection", "credential", "risk"):
                risk = max(risk, belief.get(key, 0.0) * 0.5)
        cscore = float(getattr(consensus, "score", 0.0) or 0.0)
        raw = (
            self.w_consensus * cscore
            + self.w_novelty * novelty
            - self.w_risk * risk
            + self.w_goal * goal
        )
        return max(0.0, min(1.0, raw))
