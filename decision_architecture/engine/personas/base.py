"""Persona plug-in contract.

Every domain persona implements:

    def think(state) -> ScoreVector
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping, Sequence

from decision_architecture.engine.types import Option, ScoreVector, State


class Persona(ABC):
    """Plug-in persona — PTCG / Security / ZeroAI share this interface."""

    name: str = "persona"
    role: str = "generic"
    system_prompt: str = ""

    @abstractmethod
    def think(self, state: State) -> ScoreVector:
        """Score options in state; return a ScoreVector."""
        raise NotImplementedError

    # --- helpers ---

    def score_option(self, option: Option, context: Mapping[str, Any]) -> float:
        prior = float(option.prior or 0.0)
        label = option.label.lower()
        bias = float((option.payload or {}).get("bias", 0.0))
        return max(0.0, min(1.0, 0.5 + prior * 0.3 + bias + self._label_bias(label, context)))

    def _label_bias(self, label: str, context: Mapping[str, Any]) -> float:
        return 0.0

    def _vector_from_options(
        self,
        state: State,
        *,
        stance: str,
        rationale: str,
        risks: list[str] | None = None,
        prior_vectors: Sequence[ScoreVector] | None = None,
    ) -> ScoreVector:
        ctx = {**state.context, "belief": state.belief.to_dict()}
        scores: dict[str, float] = {}
        for opt in state.options:
            scores[opt.id] = self.score_option(opt, ctx)
        if not scores:
            return ScoreVector(
                persona=self.name,
                stance=stance,
                rationale=rationale,
                confidence=0.0,
                risks=list(risks or []),
            )
        preferred = max(scores, key=scores.get)
        conf = min(0.95, 0.5 + scores[preferred] * 0.4)
        return ScoreVector(
            persona=self.name,
            scores=scores,
            preferred_id=preferred,
            confidence=conf,
            stance=stance,
            rationale=rationale,
            risks=list(risks or []),
            metadata={"role": self.role, "prior_count": len(prior_vectors or [])},
        )

    # Backward-compatible alias used by older debate code
    def evaluate(
        self,
        options: Sequence[Any],
        context: Mapping[str, Any],
        *,
        prior_opinions: Sequence[ScoreVector] | None = None,
    ) -> ScoreVector:
        state = State(
            data=dict(context.get("state", {}) if isinstance(context.get("state"), dict) else {}),
            options=list(options),
            context=dict(context),
        )
        return self.think(state)
