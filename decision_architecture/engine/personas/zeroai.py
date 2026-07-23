"""ZeroAI roster personas — Planner / Researcher / Reviewer / Executor."""

from __future__ import annotations

from typing import Any, Mapping

from decision_architecture.engine.personas.base import Persona
from decision_architecture.engine.types import ScoreVector, State


class PlannerPersona(Persona):
    name = "planner"
    role = "plan"

    def _label_bias(self, label: str, context: Mapping[str, Any]) -> float:
        return 0.22 if any(k in label for k in ("plan", "decompose", "schedule", "step")) else 0.0

    def think(self, state: State) -> ScoreVector:
        return self._vector_from_options(state, stance="plan", rationale="목표 분해·선행조건 기준.")


class ResearcherPersona(Persona):
    name = "researcher"
    role = "research"

    def _label_bias(self, label: str, context: Mapping[str, Any]) -> float:
        return 0.25 if any(k in label for k in ("research", "search", "read", "fetch", "analyze")) else 0.0

    def think(self, state: State) -> ScoreVector:
        return self._vector_from_options(state, stance="research", rationale="정보 이득 기준.")


class ReviewerPersona(Persona):
    name = "reviewer"
    role = "review"

    def _label_bias(self, label: str, context: Mapping[str, Any]) -> float:
        if any(k in label for k in ("review", "diff", "check", "lint")):
            return 0.22
        if "force" in label or "destructive" in label:
            return -0.3
        return 0.0

    def think(self, state: State) -> ScoreVector:
        return self._vector_from_options(state, stance="review", rationale="품질 게이트 기준.")


class ExecutorPersona(Persona):
    name = "executor"
    role = "execute"

    def _label_bias(self, label: str, context: Mapping[str, Any]) -> float:
        if any(k in label for k in ("execute", "run", "apply", "commit", "ship")):
            return 0.25
        return 0.15 if context.get("approved") else -0.05

    def think(self, state: State) -> ScoreVector:
        return self._vector_from_options(state, stance="execute", rationale="승인된 실행 경로.")
